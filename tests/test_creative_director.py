"""Tests for the livepilot-creative-director skill + concept + affordance packets.

These tests are documentation-level, not runtime integration tests.
They verify:

  1. The creative-director SKILL.md and its 4 references exist and parse
  2. Every concept packet (42 expected: 28 artists + 14 genres) validates
     against the packet schema in livepilot-core/references/concepts/_schema.md
  3. Every affordance packet (20 expected) validates against the schema
     in livepilot-core/references/affordances/_schema.md
  4. Cross-references resolve: concept packets' canonical_genres point at
     real genre YAMLs; canonical_artists point at real artist YAMLs
  5. Concept packets' move_family_bias uses only the 6 canonical families
  6. The creative-director SKILL.md description contains the key triggers
     that make the skill fire on creative intent

Run with:
    python -m pytest tests/test_creative_director.py -v
"""

from __future__ import annotations

import pathlib

import pytest
import yaml


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS_ROOT = REPO_ROOT / "livepilot" / "skills"
DIRECTOR_ROOT = SKILLS_ROOT / "livepilot-creative-director"
CORE_REFS = SKILLS_ROOT / "livepilot-core" / "references"
CONCEPTS_ROOT = CORE_REFS / "concepts"
AFFORDANCES_ROOT = CORE_REFS / "affordances"

# The six canonical move.family values from mcp_server/semantic_moves/*.py
CANONICAL_FAMILIES = {
    "mix",
    "arrangement",
    "transition",
    "sound_design",
    "performance",
    "device_creation",
}

# The four canonical dimensions from the-four-move-rule.md
CANONICAL_DIMENSIONS = {"structural", "rhythmic", "timbral", "spatial"}


# ---------------------------------------------------------------------------
# Skill structure
# ---------------------------------------------------------------------------


def test_director_skill_exists():
    skill = DIRECTOR_ROOT / "SKILL.md"
    assert skill.exists(), f"Creative Director SKILL.md missing: {skill}"


def test_director_skill_frontmatter():
    skill = DIRECTOR_ROOT / "SKILL.md"
    text = skill.read_text()
    assert text.startswith("---\n"), "SKILL.md must start with YAML frontmatter"
    end = text.find("\n---\n", 4)
    assert end > 0, "SKILL.md frontmatter must close"
    fm = yaml.safe_load(text[4:end])
    assert fm["name"] == "livepilot-creative-director"
    assert len(fm["description"]) <= 1024, "Description over 1024 char limit"
    # Description must contain creative-intent triggers so the skill fires
    desc_lower = fm["description"].lower()
    for keyword in ["creative", "like x", "develop", "more interesting"]:
        assert keyword in desc_lower, f"Description missing keyword: {keyword}"


def test_director_reference_files_exist():
    refs = DIRECTOR_ROOT / "references"
    expected = {
        "creative-brief-template.md",
        "move-family-diversity-rule.md",
        "anti-repetition-rules.md",
        "the-four-move-rule.md",
    }
    actual = {p.name for p in refs.glob("*.md")}
    missing = expected - actual
    assert not missing, f"Missing reference files: {missing}"


# ---------------------------------------------------------------------------
# Concept packet schema
# ---------------------------------------------------------------------------


def _load_concept_packets():
    packets = {}
    for subdir in ("artists", "genres"):
        for p in sorted((CONCEPTS_ROOT / subdir).glob("*.yaml")):
            packets[p.stem] = yaml.safe_load(p.read_text())
    return packets


CONCEPT_REQUIRED_FIELDS = {
    "id",
    "name",
    "type",
    "sonic_identity",
    "reach_for",
    "avoid",
    "evaluation_bias",
    "move_family_bias",
    "dimensions_in_scope",
    "novelty_budget_default",
}


def test_concept_packets_count():
    artists = list((CONCEPTS_ROOT / "artists").glob("*.yaml"))
    genres = list((CONCEPTS_ROOT / "genres").glob("*.yaml"))
    assert len(artists) == 28, f"Expected 28 artist packets, found {len(artists)}"
    assert len(genres) == 14, f"Expected 14 genre packets, found {len(genres)}"


def test_concept_packets_parse_and_have_required_fields():
    packets = _load_concept_packets()
    assert packets, "No concept packets loaded"
    for slug, d in packets.items():
        missing = CONCEPT_REQUIRED_FIELDS - set(d.keys())
        assert not missing, f"{slug}: missing fields {missing}"


def test_concept_packets_types_valid():
    packets = _load_concept_packets()
    for slug, d in packets.items():
        assert d["type"] in {"artist", "genre", "hybrid"}, (
            f"{slug}: invalid type {d['type']}"
        )


def test_artist_packets_have_canonical_genres():
    for p in sorted((CONCEPTS_ROOT / "artists").glob("*.yaml")):
        d = yaml.safe_load(p.read_text())
        assert d.get("canonical_genres"), (
            f"{p.stem}: artist packet must have canonical_genres populated"
        )


def test_genre_packets_have_canonical_artists():
    for p in sorted((CONCEPTS_ROOT / "genres").glob("*.yaml")):
        d = yaml.safe_load(p.read_text())
        # Canonical_artists may be empty for very new genres — allow but warn
        # For the shipped 14, each should name at least one canonical artist
        # EXCEPTIONS: trap, dubstep in some cases — but we currently have them
        if p.stem in {"trap"}:
            # Trap has canonical_artists: [] by design (genre more than artist-defined)
            continue
        assert d.get("canonical_artists"), (
            f"{p.stem}: genre packet must have canonical_artists populated"
        )


def test_move_family_bias_uses_canonical_families():
    packets = _load_concept_packets()
    for slug, d in packets.items():
        bias = d["move_family_bias"]
        favor = set(bias.get("favor", []))
        depri = set(bias.get("deprioritize", []))
        invalid_favor = favor - CANONICAL_FAMILIES
        invalid_depri = depri - CANONICAL_FAMILIES
        assert not invalid_favor, (
            f"{slug}: favor has non-canonical families {invalid_favor}"
        )
        assert not invalid_depri, (
            f"{slug}: deprioritize has non-canonical families {invalid_depri}"
        )
        overlap = favor & depri
        assert not overlap, f"{slug}: favor and deprioritize overlap: {overlap}"


def test_dimensions_in_scope_uses_canonical_dimensions():
    packets = _load_concept_packets()
    for slug, d in packets.items():
        in_scope = set(d["dimensions_in_scope"])
        deprioritized = set(d.get("dimensions_deprioritized", []))
        invalid_in = in_scope - CANONICAL_DIMENSIONS
        invalid_depri = deprioritized - CANONICAL_DIMENSIONS
        assert not invalid_in, (
            f"{slug}: dimensions_in_scope has non-canonical values {invalid_in}"
        )
        assert not invalid_depri, (
            f"{slug}: dimensions_deprioritized has non-canonical values "
            f"{invalid_depri}"
        )


def test_novelty_budget_in_valid_range():
    packets = _load_concept_packets()
    for slug, d in packets.items():
        nb = d["novelty_budget_default"]
        assert isinstance(nb, (int, float)), (
            f"{slug}: novelty_budget_default must be numeric"
        )
        assert 0.0 <= nb <= 1.0, f"{slug}: novelty_budget {nb} outside [0.0, 1.0]"


def test_artist_to_genre_refs_resolve_or_alias():
    """Artist packets' canonical_genres should resolve to either a genre
    YAML id or an alias. Genres we haven't YAML-ified yet (downtempo,
    boom_bap, lo_fi, etc.) are tolerated as narrative-only references —
    see TODO in test_missing_genre_yamls_as_todo below."""
    genre_lookup = set()
    for p in (CONCEPTS_ROOT / "genres").glob("*.yaml"):
        d = yaml.safe_load(p.read_text())
        genre_lookup.add(d["id"])
        genre_lookup.add(p.stem)
        for alias in d.get("aliases", []) or []:
            # Normalize alias to the slug form used in artist refs
            genre_lookup.add(alias.replace(" ", "_").replace("-", "_"))
            genre_lookup.add(alias.replace(" ", "-"))

    unresolved = []
    for p in (CONCEPTS_ROOT / "artists").glob("*.yaml"):
        d = yaml.safe_load(p.read_text())
        for genre_ref in d.get("canonical_genres", []):
            if genre_ref not in genre_lookup:
                unresolved.append((p.stem, genre_ref))

    # Record the count so we can track convergence over time — this assertion
    # succeeds for any bounded value, but any regression above the current
    # threshold flags as a test failure.
    CURRENT_UNRESOLVED_THRESHOLD = 40  # 2026-04-23 baseline
    assert len(unresolved) <= CURRENT_UNRESOLVED_THRESHOLD, (
        f"Unresolved artist→genre refs ({len(unresolved)}) exceeded threshold "
        f"{CURRENT_UNRESOLVED_THRESHOLD}. Reduce the threshold or add YAMLs: "
        f"{unresolved[:8]}"
    )


def test_genre_to_artist_refs_resolve():
    """Genres' canonical_artists MUST resolve — the artist YAML set is
    complete (28 packets), so any unresolved ref is a typo."""
    artist_slugs = {p.stem for p in (CONCEPTS_ROOT / "artists").glob("*.yaml")}

    unresolved = []
    for p in (CONCEPTS_ROOT / "genres").glob("*.yaml"):
        d = yaml.safe_load(p.read_text())
        for artist_ref in d.get("canonical_artists", []) or []:
            if artist_ref not in artist_slugs:
                unresolved.append((p.stem, artist_ref))

    assert not unresolved, f"Unresolved artist cross-refs: {unresolved}"


@pytest.mark.xfail(
    reason="TODO(pr-2.6): Genre YAMLs not yet created for downtempo, boom_bap, "
    "lo_fi, synthwave, techno, detroit_techno, soul, jungle (aliased via "
    "drum-and-bass), footwork, deep_house, french_house, disco, electronic, "
    "electronica, cinematic, hyperpop, drone, bass_music, soulful_house, "
    "acid_techno, nu_disco, juke. Artists reference them per their narrative "
    ".md section headings. Either create the YAMLs or trim the artist refs."
)
def test_all_artist_genre_refs_resolve_strictly():
    """Strict version of test_artist_to_genre_refs_resolve_or_alias.
    Currently xfailing — will convert to required pass when all genre
    YAMLs exist."""
    genre_lookup = set()
    for p in (CONCEPTS_ROOT / "genres").glob("*.yaml"):
        d = yaml.safe_load(p.read_text())
        genre_lookup.add(d["id"])

    unresolved = []
    for p in (CONCEPTS_ROOT / "artists").glob("*.yaml"):
        d = yaml.safe_load(p.read_text())
        for genre_ref in d.get("canonical_genres", []):
            if genre_ref not in genre_lookup:
                unresolved.append((p.stem, genre_ref))

    assert not unresolved, f"Unresolved (strict): {unresolved}"


# ---------------------------------------------------------------------------
# Affordance packet schema
# ---------------------------------------------------------------------------


AFFORDANCE_REQUIRED_FIELDS = {
    "id",
    "name",
    "type",
    "category",
    "atlas_search_query",
    "musical_roles",
    "strong_for",
    "risky_for",
    "pairings",
    "remeasure",
    "dimensional_impact",
    "appears_in_packets",
}


def test_affordance_packets_count():
    affordances = list((AFFORDANCES_ROOT / "devices").glob("*.yaml"))
    assert len(affordances) >= 20, (
        f"Expected at least 20 affordance packets, found {len(affordances)}"
    )


def test_affordance_packets_parse_and_have_required_fields():
    for p in sorted((AFFORDANCES_ROOT / "devices").glob("*.yaml")):
        d = yaml.safe_load(p.read_text())
        missing = AFFORDANCE_REQUIRED_FIELDS - set(d.keys())
        assert not missing, f"{p.stem}: missing fields {missing}"


def test_affordance_types_valid():
    valid_types = {"effect", "instrument", "utility", "rack"}
    for p in sorted((AFFORDANCES_ROOT / "devices").glob("*.yaml")):
        d = yaml.safe_load(p.read_text())
        assert d["type"] in valid_types, (
            f"{p.stem}: invalid type {d['type']} (expected one of {valid_types})"
        )


def test_affordance_no_stale_atlas_uri():
    """PR 3 quality fix — the field was renamed from atlas_uri to
    atlas_search_query. Prevent regression."""
    for p in sorted((AFFORDANCES_ROOT / "devices").glob("*.yaml")):
        d = yaml.safe_load(p.read_text())
        assert "atlas_uri" not in d, (
            f"{p.stem}: stale atlas_uri field — rename to atlas_search_query"
        )
        # atlas_search_query must be a plain search term, not a "query:..." URI
        query = d["atlas_search_query"]
        assert not query.startswith("query:"), (
            f"{p.stem}: atlas_search_query must be a plain term, not a URI hint"
        )


def test_affordance_dimensional_impact_fields():
    valid_levels = {"none", "low", "low-moderate", "moderate", "high"}
    for p in sorted((AFFORDANCES_ROOT / "devices").glob("*.yaml")):
        d = yaml.safe_load(p.read_text())
        impact = d["dimensional_impact"]
        for dim in CANONICAL_DIMENSIONS:
            assert dim in impact, f"{p.stem}: missing dimensional_impact.{dim}"
            level = impact[dim]
            assert level in valid_levels, (
                f"{p.stem}: dimensional_impact.{dim} = {level!r} "
                f"not in {valid_levels}"
            )


def test_affordance_appears_in_packets_artists_resolve():
    """Every artist referenced in affordance appears_in_packets must exist.
    Artist YAMLs are complete (28), so any unresolved ref is a typo."""
    artist_slugs = {p.stem for p in (CONCEPTS_ROOT / "artists").glob("*.yaml")}

    unresolved = []
    for p in (AFFORDANCES_ROOT / "devices").glob("*.yaml"):
        d = yaml.safe_load(p.read_text())
        appears = d.get("appears_in_packets", {})
        for artist in appears.get("artists", []) or []:
            if artist not in artist_slugs:
                unresolved.append((p.stem, artist))

    assert not unresolved, f"Unresolved appears_in_packets.artists: {unresolved}"


def test_affordance_appears_in_packets_genres_tolerated():
    """Genre refs in affordances may point at narrative-only genres (same
    issue as artist→genre refs). Apply the same threshold."""
    genre_slugs = {p.stem for p in (CONCEPTS_ROOT / "genres").glob("*.yaml")}

    unresolved = []
    for p in (AFFORDANCES_ROOT / "devices").glob("*.yaml"):
        d = yaml.safe_load(p.read_text())
        appears = d.get("appears_in_packets", {})
        for genre in appears.get("genres", []) or []:
            if genre not in genre_slugs:
                unresolved.append((p.stem, genre))

    CURRENT_UNRESOLVED_THRESHOLD = 30  # 2026-04-23 baseline
    assert len(unresolved) <= CURRENT_UNRESOLVED_THRESHOLD, (
        f"Unresolved affordance→genre refs ({len(unresolved)}) exceeded "
        f"threshold {CURRENT_UNRESOLVED_THRESHOLD}: {unresolved[:8]}"
    )


# ---------------------------------------------------------------------------
# Schema files exist
# ---------------------------------------------------------------------------


def test_concept_schema_exists():
    schema = CONCEPTS_ROOT / "_schema.md"
    assert schema.exists(), f"Concept schema missing: {schema}"


def test_affordance_schema_exists():
    schema = AFFORDANCES_ROOT / "_schema.md"
    assert schema.exists(), f"Affordance schema missing: {schema}"


# ---------------------------------------------------------------------------
# Cross-skill integration
# ---------------------------------------------------------------------------


def test_director_references_concept_packets():
    """The director's SKILL.md should point at the structured packets
    (PR 2 integration), not only the narrative .md files."""
    skill = (DIRECTOR_ROOT / "SKILL.md").read_text()
    assert "concepts/artists" in skill, (
        "Director SKILL.md must reference concepts/artists/ YAML packets"
    )
    assert "concepts/genres" in skill, (
        "Director SKILL.md must reference concepts/genres/ YAML packets"
    )


def test_director_references_affordances():
    """PR 3 integration — the director's SKILL.md should reference the
    affordance YAMLs in Phase 6."""
    skill = (DIRECTOR_ROOT / "SKILL.md").read_text()
    assert "affordances/" in skill or "Affordance lookup" in skill, (
        "Director SKILL.md must reference affordance packets in Phase 6"
    )


def test_evaluation_skill_has_artistic_dimensions():
    """PR 4 integration — livepilot-evaluation should document the
    Family B artistic dimensions."""
    eval_skill = (SKILLS_ROOT / "livepilot-evaluation" / "SKILL.md").read_text()
    for dim in [
        "style_fit",
        "distinctiveness",
        "motif_coherence",
        "section_contrast",
        "restraint",
    ]:
        assert dim in eval_skill, (
            f"livepilot-evaluation/SKILL.md missing artistic dimension: {dim}"
        )


def test_evaluation_skill_has_verdict_taxonomy():
    """PR 4 integration — the 5 verdicts must be documented."""
    eval_skill = (SKILLS_ROOT / "livepilot-evaluation" / "SKILL.md").read_text()
    for verdict in [
        "safe_win",
        "bold_win",
        "interesting_failure",
        "identity_break",
        "generic_fallback",
    ]:
        assert verdict in eval_skill, (
            f"livepilot-evaluation/SKILL.md missing verdict: {verdict}"
        )


def test_memory_guide_has_promotion_rubric():
    """PR 5 integration — memory-guide must have the verdict-driven
    promotion rubric."""
    guide = (CORE_REFS / "memory-guide.md").read_text()
    assert "Reflection Promotion Rubric" in guide or "Promotion matrix" in guide, (
        "memory-guide.md must include the verdict-driven promotion rubric"
    )
    for verdict in ["safe_win", "bold_win", "identity_break", "generic_fallback"]:
        assert verdict in guide, (
            f"memory-guide.md promotion rubric missing verdict: {verdict}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

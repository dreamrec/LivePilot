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

# The seven canonical move.family values — six from
# mcp_server/semantic_moves/*.py plus `sample` from
# mcp_server/sample_engine/moves.py. Verified against
# list_semantic_moves() runtime on v1.18.0 ship: 33 moves, 7 domains.
CANONICAL_FAMILIES = {
    "mix",
    "arrangement",
    "transition",
    "sound_design",
    "performance",
    "device_creation",
    "sample",
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


# ---------------------------------------------------------------------------
# v1.18.1 patch-target regression guards
# ---------------------------------------------------------------------------


def test_ping_pong_delay_is_documented_as_echo_mode():
    """v1.18.1 #4: Ping Pong Delay is NOT a standalone device in Live 12 —
    search_browser(audio_effects, "Ping Pong Delay") returns empty. The
    affordance MUST document this and redirect to Echo with Channel Mode=1.
    Regression guard: no future edit can silently re-assert standalone status."""
    p = AFFORDANCES_ROOT / "devices" / "ping-pong-delay.yaml"
    d = yaml.safe_load(p.read_text())

    # atlas_search_query must be "Echo" (the actually-loadable device) — a
    # query for "Ping Pong Delay" returns empty on Live 12.
    assert d["atlas_search_query"] == "Echo", (
        f"ping-pong-delay.atlas_search_query must be 'Echo', "
        f"got {d['atlas_search_query']!r}. Ping Pong Delay is not a "
        f"standalone device; the search target is Echo."
    )

    # notes must explain the mode-alias relationship
    notes = d.get("notes", "").lower()
    assert "echo" in notes, "notes must reference Echo as the real device"
    assert "channel mode" in notes, (
        "notes must explain the 'Channel Mode' parameter (value 1 = Ping Pong)"
    )
    assert "not a standalone" in notes or "mode of echo" in notes, (
        "notes must explicitly state this is not a standalone Live 12 device"
    )


def test_auto_filter_ranges_are_normalized_for_modern_class():
    """v1.18.1 #5: Modern AutoFilter2 class uses 0-1 normalized for Frequency
    and Resonance (confirmed live: raw 0.45 → value_string '448 Hz'). The
    legacy 20-135 range from pre-2010 Auto Filter doesn't apply. Regression
    guard: no future edit can reintroduce legacy Hz values."""
    p = AFFORDANCES_ROOT / "devices" / "auto-filter.yaml"
    d = yaml.safe_load(p.read_text())

    for band_name in ("subtle_ranges", "moderate_ranges", "aggressive_ranges"):
        band = d.get(band_name, {})
        freq_range = band.get("frequency")
        if freq_range is None:
            continue  # frequency not specified in this band — acceptable
        lo, hi = freq_range
        assert 0 <= lo <= 1, (
            f"auto-filter.{band_name}.frequency[0] = {lo} — must be 0-1 "
            f"normalized (modern AutoFilter2), not legacy Hz value"
        )
        assert 0 <= hi <= 1, (
            f"auto-filter.{band_name}.frequency[1] = {hi} — must be 0-1 "
            f"normalized (modern AutoFilter2), not legacy Hz value"
        )

        # Resonance is also 0-1 on modern, not 0-1.25 legacy
        res_range = band.get("resonance")
        if res_range is not None:
            r_lo, r_hi = res_range
            assert 0 <= r_hi <= 1.0, (
                f"auto-filter.{band_name}.resonance[1] = {r_hi} — must be "
                f"0-1 on AutoFilter2 (legacy was 0-1.25)"
            )


def test_low_novelty_escape_hatch_documented():
    """v1.18.1 #12: 3-plan diversity rule must have a documented escape
    hatch for low-novelty_budget requests ('keep the vibe, just cleaner').
    Current bug: the rule demands 3 distinct families even when the ask is
    a cleanup that naturally lives entirely in the mix family."""
    diversity_rule = (
        DIRECTOR_ROOT / "references" / "move-family-diversity-rule.md"
    ).read_text().lower()
    # Must mention low-novelty threshold explicitly
    assert "novelty_budget" in diversity_rule, (
        "move-family-diversity-rule.md must reference novelty_budget"
    )
    # Must have a clause about narrow mix-only acceptance
    lowish = ("0.35" in diversity_rule or "0.3" in diversity_rule
              or "< 0.35" in diversity_rule or "low novelty" in diversity_rule)
    assert lowish, (
        "move-family-diversity-rule.md must document that low novelty_budget "
        "(<0.35) allows 1-2 mix-family plans as honest coverage — "
        "without this clause the rule incorrectly demands 3 families on "
        "cleanup asks like 'keep the vibe, just cleaner'"
    )


def test_create_experiment_auto_proposal_no_m0_bug():
    """v1.18.1 #1 HIGH SEV: create_experiment auto-proposal was taking
    the FIRST CHARACTER of each move_id (m[0]) instead of the whole
    string. Result: experiments built with move_ids like 't', 'w', 'm'
    that fail at run_experiment with 'Move t not found'.

    The bug was a Python unpacking trap: `[m[0] for m, _ in scored]`
    where `m` is already the move_id string — `m[0]` indexes into it.

    Regression guard via source-level pattern scan, because the tool
    itself requires an MCP Context to call directly."""
    path = REPO_ROOT / "mcp_server" / "experiment" / "tools.py"
    text = path.read_text()
    # The exact bug pattern
    assert "m[0] for m, _" not in text, (
        "Regression: auto-proposal selector reintroduced the m[0] bug. "
        "Should be `[m for m, _ in scored[:limit]]` (strip the [0]). "
        "See CHANGELOG v1.18.0 Known Issues #1 for the live repro."
    )
    # The function MUST produce move_ids longer than 1 char on realistic input
    # — guard against a variant of the same bug (e.g. m[:1] or slice(0,1)).
    # This is best-effort pattern scan, not exhaustive.
    for bad_pattern in ["m[:1]", "[0:1]", "slice(0, 1)"]:
        assert bad_pattern not in text, (
            f"Regression: auto-proposal has suspicious pattern {bad_pattern!r}"
        )


def test_create_experiment_auto_proposal_functional():
    """v1.18.1 #1 functional check: the keyword-overlap scoring logic
    produces real multi-character move_ids. Tests the pure scoring logic
    directly (not the MCP tool wrapper) by re-implementing the fix as a
    local mirror and confirming it returns valid registry move_ids."""
    from mcp_server.semantic_moves import registry

    all_moves = list(registry._REGISTRY.values())
    assert all_moves, "registry must be non-empty for this test to be useful"
    # Pick a representative move_id and confirm it's multi-char
    sample_move = all_moves[0]
    assert len(sample_move.move_id) > 1, (
        f"sample move_id {sample_move.move_id!r} should be multi-char"
    )

    # Re-implement the fixed logic locally (mirror of tools.py:250-267)
    request_lower = "deepen the dub aesthetic on this".lower()
    request_words = set(request_lower.split())
    scored = []
    for move in all_moves:
        score = 0.0
        move_words = set(move.move_id.replace("_", " ").split())
        intent_words = set(move.intent.lower().split())
        overlap = request_words & (move_words | intent_words)
        score += len(overlap) * 0.3
        for dim in move.targets:
            if dim in request_lower:
                score += 0.2
        if score > 0.1:
            scored.append((move.move_id, score))
    scored.sort(key=lambda x: -x[1])
    move_ids_correct = [m for m, _ in scored[:3]]
    move_ids_buggy = [m[0] for m, _ in scored[:3]]

    # Both shapes may be empty if nothing scored — that's acceptable here.
    # But if anything DID score, the correct shape returns multi-char
    # move_ids while the buggy shape returns single chars.
    if scored:
        assert all(len(mid) > 1 for mid in move_ids_correct), (
            f"Fixed path must return multi-char move_ids. "
            f"Got: {move_ids_correct}"
        )
        # Sanity: the buggy shape WOULD have returned single chars,
        # confirming our repro is valid
        assert all(len(mid) == 1 for mid in move_ids_buggy), (
            f"Buggy shape repro failed — test setup is wrong. "
            f"Got: {move_ids_buggy}"
        )


def test_composer_dub_techno_prompt_avoids_drop_scaffold():
    """v1.18.1 #2 HIGH SEV: propose_composer_branches was producing generic
    techno scaffold (Intro→Build→Drop→Breakdown→Drop2→Outro + 6 standard
    layers) for dub-techno prompts referencing Basic Channel. Dub-techno
    is a continuous-evolution aesthetic with NO drop structure — the
    packet's arrangement_idioms say 'slow reveal, subtraction before
    addition, return deeper not louder'.

    Live repro from v1.18.0 testing with prompt:
      'dub techno track like Basic Channel at 120 BPM'
    produced sections: Intro, Build, Drop, Breakdown, Drop 2, Outro.
    This test guards against regression to that behavior."""
    from mcp_server.composer.prompt_parser import parse_prompt
    from mcp_server.composer.layer_planner import plan_sections

    intent = parse_prompt("dub techno track like Basic Channel at 120 BPM")
    sections = plan_sections(intent)
    section_names = [s["name"] for s in sections]

    # CORE assertion: no drop structure
    assert "Drop" not in section_names, (
        f"Dub-techno prompts must not produce Drop-based scaffold — "
        f"drops are foreign to the aesthetic. Got: {section_names}"
    )
    assert "Drop 2" not in section_names, (
        f"Dub-techno must not have a 'Drop 2' — got {section_names}"
    )
    # Must still have a reasonable section count (not 0 sections)
    assert len(section_names) >= 3, (
        f"need at least 3 sections in scaffold, got {len(section_names)}: "
        f"{section_names}"
    )

    # Dub-techno identity must be preserved — either as primary genre or sub_genre
    combined = f"{intent.genre} {intent.sub_genre}".lower()
    assert "dub" in combined, (
        f"Intent must retain dub-techno identity. "
        f"genre={intent.genre!r}, sub_genre={intent.sub_genre!r}"
    )

    # Tempo from prompt (120) must stick — not be overwritten by genre default
    assert intent.tempo == 120, (
        f"Explicit tempo '120 BPM' from prompt must be preserved, "
        f"got {intent.tempo}"
    )


def test_propose_composer_branches_honors_explicit_count():
    """v1.18.1 #9: propose_composer_branches silently clamped to freshness-
    gated strategy count even when caller explicitly requested more.
    Live repro: requested count=3 at freshness=0.6 returned only 2 seeds
    (canonical + energy_shift; layer_contrast gated behind freshness>=0.7).

    Fix: explicit count should override the freshness gate — if caller
    asks for 3, they get 3 (raising freshness internally to admit them)."""
    from mcp_server.composer.branch_producer import propose_composer_branches

    # Exact repro of v1.18.0 live test
    results = propose_composer_branches(
        request_text="dub techno track at 120 BPM",
        kernel={"freshness": 0.6},  # below 0.7 threshold for layer_contrast
        count=3,
    )
    assert len(results) == 3, (
        f"Requested count=3 at freshness=0.6 should return 3 seeds "
        f"(explicit count overrides freshness gate). Got {len(results)}: "
        f"{[s[0].seed_id for s in results]}"
    )


def test_director_phase6_records_ledger_marker():
    """v1.18.1 #3 MED-HIGH SEV: director's raw-tool-call execution path
    bypasses the action ledger, making get_last_move return {} and
    breaking anti-repetition on subsequent creative turns.

    Minimum fix: Phase 6 must explicitly document that raw-tool execution
    requires a manual ledger marker via add_session_memory OR memory_learn.
    Full architectural fix (route all execution through semantic_move) is
    deferred to v1.19."""
    skill = (DIRECTOR_ROOT / "SKILL.md").read_text()
    assert "### Phase 6" in skill, "director must have a Phase 6 section"
    phase_6 = skill.split("### Phase 6")[1].split("### Phase 7")[0]
    # Must reference manual ledger writing
    has_session_memory = "add_session_memory" in phase_6 or "session_memory" in phase_6
    has_ledger_guidance = "ledger" in phase_6.lower()
    assert has_session_memory and has_ledger_guidance, (
        "Phase 6 must document add_session_memory as the ledger-marker "
        "for raw-tool execution paths. Currently missing — get_last_move "
        "returns empty on creative turns that bypass semantic_move."
    )


def test_anti_repetition_has_state_inference_fallback():
    """v1.18.1 #3: When the action ledger is empty because the director
    used raw tool calls (not semantic_move commits), anti-repetition
    must fall back to session-state inference — scan currently-loaded
    devices and track-assignment deltas to infer recent family activity.
    Without this fallback, the director is blind to its own recent
    actions across turns."""
    rules = (DIRECTOR_ROOT / "references" / "anti-repetition-rules.md").read_text().lower()
    # Must reference the fallback mechanism explicitly
    fallback_keywords = ("state inference", "session state", "ledger is empty",
                        "ledger empty", "state-based inference")
    assert any(kw in rules for kw in fallback_keywords), (
        "anti-repetition-rules.md must document the state-inference "
        "fallback for when get_last_move / memory_list is empty"
    )


def test_batch_set_parameters_schema_documented():
    """v1.18.1 bonus: the batch_set_parameters schema requires
    {'Name': {'value': v}}, not {'Name': v}. Live verification bit me on
    this. Regression guard: the core skill or creative-brief-template
    must document the correct shape."""
    # Check multiple likely locations for the doc
    candidates = [
        SKILLS_ROOT / "livepilot-core" / "SKILL.md",
        DIRECTOR_ROOT / "SKILL.md",
        DIRECTOR_ROOT / "references" / "creative-brief-template.md",
        CORE_REFS / "ableton-workflow-patterns.md",
    ]
    found = False
    for candidate in candidates:
        if not candidate.exists():
            continue
        text = candidate.read_text()
        if "batch_set_parameters" in text and '"value"' in text:
            found = True
            break
    assert found, (
        "batch_set_parameters schema must be documented somewhere in the "
        "core skill docs — at least one location should show the "
        "{'Name': {'value': v}} form"
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

"""Tests for v1.19 Item B — hybrid concept packet compilation.

When the user says "Basic Channel meets Dilla swing" or
"Villalobos but sparse like Gas", the director needs to merge
two (or more) concept packets into a single brief. Pre-v1.19
this was LLM ad-hoc reasoning with no guarantees about
contradiction handling (e.g., Gas deprioritizes rhythmic,
Dilla emphasizes rhythmic → no explicit rule for resolution).

``compile_hybrid_brief`` implements the merge rules documented
in docs/plans/v1.19-structural-plan.md §3:

  sonic_identity / reach_for / avoid / *_idioms / sample_roles
      → UNION (deduplicated, first-packet order preserved)
  evaluation_bias.target_dimensions
      → WEIGHTED AVERAGE (default uniform)
  evaluation_bias.protect
      → MAX per dimension (stricter floor wins)
  move_family_bias.favor
      → INTERSECTION preferred, UNION fallback with warning
  move_family_bias.deprioritize
      → INTERSECTION (deprioritize only if BOTH do)
  dimensions_in_scope
      → UNION (widened)
  dimensions_deprioritized
      → INTERSECTION (only if BOTH do)
  novelty_budget_default
      → MAX (hybrid asks skew exploratory)
  tempo_hint
      → NEAREST-OVERLAP, warning on disjoint ranges
"""

from __future__ import annotations

import pytest


# ── load_packet ──────────────────────────────────────────────────────────────


class TestLoadPacket:

    def test_loads_artist_packet_by_filename_stem(self):
        from mcp_server.creative_director.hybrid import load_packet

        packet = load_packet("basic-channel")
        assert packet is not None
        assert packet["type"] == "artist"
        assert packet["id"] == "dub_techno__basic_channel"

    def test_loads_genre_packet_by_filename_stem(self):
        from mcp_server.creative_director.hybrid import load_packet

        packet = load_packet("ambient")
        assert packet is not None
        assert packet["type"] == "genre"

    def test_loads_via_underscore_to_hyphen_normalization(self):
        """'basic_channel' should resolve to basic-channel.yaml."""
        from mcp_server.creative_director.hybrid import load_packet

        packet = load_packet("basic_channel")
        assert packet is not None
        assert packet["id"] == "dub_techno__basic_channel"

    def test_loads_via_alias(self):
        """j-dilla.yaml lists 'dilla' among its aliases."""
        from mcp_server.creative_director.hybrid import load_packet

        packet = load_packet("dilla")
        assert packet is not None
        assert packet["type"] == "artist"

    def test_returns_none_when_missing(self):
        from mcp_server.creative_director.hybrid import load_packet

        assert load_packet("this-packet-definitely-does-not-exist") is None


# ── compile_hybrid_brief — input validation ─────────────────────────────────


class TestHybridCompilationInputValidation:

    def test_requires_at_least_two_packets(self):
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        with pytest.raises(ValueError, match="at least 2"):
            compile_hybrid_brief(["basic-channel"])

    def test_raises_on_missing_packet(self):
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        with pytest.raises(ValueError, match="not found"):
            compile_hybrid_brief(["basic-channel", "does-not-exist"])

    def test_weights_length_must_match_packets(self):
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        with pytest.raises(ValueError, match="weights"):
            compile_hybrid_brief(
                ["basic-channel", "j-dilla"],
                weights=[0.5, 0.3, 0.2],
            )


# ── compile_hybrid_brief — UNION rules ──────────────────────────────────────


class TestHybridUnionRules:

    def test_avoid_lists_are_unioned(self):
        """BC avoids 'bright top-end'; Dilla avoids 'quantized drums'.
        Hybrid avoid must contain items from BOTH."""
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        brief = compile_hybrid_brief(["basic-channel", "j-dilla"])

        avoid_lower = [a.lower() for a in brief["avoid"]]
        assert any("bright" in a for a in avoid_lower), \
            "BC's 'bright top-end' avoidance missing from hybrid"
        assert any("quantized" in a for a in avoid_lower), \
            "Dilla's 'quantized drums' avoidance missing from hybrid"

    def test_avoid_is_also_exposed_as_anti_patterns(self):
        """For compat with check_brief_compliance which reads 'anti_patterns'."""
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        brief = compile_hybrid_brief(["basic-channel", "j-dilla"])
        assert "anti_patterns" in brief
        assert set(brief["anti_patterns"]) == set(brief["avoid"])

    def test_sonic_identity_union_deduplicates(self):
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        brief = compile_hybrid_brief(["basic-channel", "j-dilla"])
        # duplicate-free
        assert len(brief["sonic_identity"]) == len(set(brief["sonic_identity"]))
        # has items from both
        sonic = " ".join(brief["sonic_identity"]).lower()
        assert "space" in sonic or "chord" in sonic  # BC-like
        assert "off-grid" in sonic or "sample" in sonic  # Dilla-like

    def test_reach_for_instruments_unioned(self):
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        brief = compile_hybrid_brief(["basic-channel", "j-dilla"])
        instruments = brief["reach_for"]["instruments"]
        # BC has Drift; Dilla has Electric Keyboards
        assert "Drift" in instruments
        assert "Electric Keyboards" in instruments

    def test_dimensions_in_scope_unioned(self):
        """BC: [timbral, spatial, structural]; Dilla: [rhythmic, timbral, structural].
        Hybrid scope should span all 4 (union)."""
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        brief = compile_hybrid_brief(["basic-channel", "j-dilla"])
        scope = set(brief["dimensions_in_scope"])
        assert "rhythmic" in scope  # from Dilla
        assert "spatial" in scope   # from BC
        assert "timbral" in scope   # both
        assert "structural" in scope


# ── compile_hybrid_brief — INTERSECTION rules ───────────────────────────────


class TestHybridIntersectionRules:

    def test_deprioritized_dimensions_intersect_to_empty(self):
        """BC deprioritizes 'rhythmic'; Dilla deprioritizes 'spatial'.
        Neither is deprioritized by BOTH — so the intersection is empty,
        meaning the hybrid does NOT deprioritize either dimension."""
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        brief = compile_hybrid_brief(["basic-channel", "j-dilla"])
        assert brief["dimensions_deprioritized"] == []

    def test_move_family_deprioritize_intersection(self):
        """BC deprioritizes [transition, performance]; Dilla deprioritizes
        [mix, performance]. Intersection = [performance]."""
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        brief = compile_hybrid_brief(["basic-channel", "j-dilla"])
        assert brief["move_family_bias"]["deprioritize"] == ["performance"]

    def test_move_family_favor_uses_intersection_when_nonempty(self):
        """BC favor = [sound_design, device_creation, mix]; Dilla favor =
        [arrangement, sound_design, device_creation]. Intersection =
        [sound_design, device_creation]."""
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        brief = compile_hybrid_brief(["basic-channel", "j-dilla"])
        favor = set(brief["move_family_bias"]["favor"])
        assert favor == {"sound_design", "device_creation"}

    def test_move_family_favor_union_fallback_when_intersection_empty(self):
        """If the two packets' favor lists are disjoint, the intersection
        is empty — fall back to UNION and surface a warning.

        Gas favor and Dilla favor may share nothing; we construct a
        synthetic case to guarantee disjoint favor lists."""
        from mcp_server.creative_director.hybrid import _compile_from_packets

        p1 = {
            "name": "P1", "id": "p1", "type": "artist", "avoid": [],
            "sonic_identity": [], "reach_for": {}, "evaluation_bias": {},
            "move_family_bias": {"favor": ["arrangement"], "deprioritize": []},
        }
        p2 = {
            "name": "P2", "id": "p2", "type": "artist", "avoid": [],
            "sonic_identity": [], "reach_for": {}, "evaluation_bias": {},
            "move_family_bias": {"favor": ["mix"], "deprioritize": []},
        }
        brief = _compile_from_packets([p1, p2], packet_ids=["p1", "p2"])
        favor = set(brief["move_family_bias"]["favor"])
        # Union fallback — both survive
        assert favor == {"arrangement", "mix"}
        # Warning surfaced
        assert any("favor" in w.lower() and "union" in w.lower()
                   for w in brief["warnings"])


# ── compile_hybrid_brief — WEIGHTED AVERAGE / MAX rules ─────────────────────


class TestHybridNumericRules:

    def test_target_dimensions_weighted_average_default_uniform(self):
        """BC groove=0.12, Dilla groove=0.26 → uniform hybrid groove ≈ 0.19."""
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        brief = compile_hybrid_brief(["basic-channel", "j-dilla"])
        groove = brief["evaluation_bias"]["target_dimensions"]["groove"]
        assert groove == pytest.approx(0.19, abs=0.005)

    def test_target_dimensions_respects_custom_weights(self):
        """75/25 weighting toward BC should pull groove closer to BC's 0.12."""
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        brief = compile_hybrid_brief(
            ["basic-channel", "j-dilla"], weights=[0.75, 0.25],
        )
        groove = brief["evaluation_bias"]["target_dimensions"]["groove"]
        # 0.75*0.12 + 0.25*0.26 = 0.155
        assert groove == pytest.approx(0.155, abs=0.005)

    def test_protect_uses_max_per_dimension(self):
        """BC protect low_end=0.80, Dilla=0.75 → MAX = 0.80."""
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        brief = compile_hybrid_brief(["basic-channel", "j-dilla"])
        assert brief["evaluation_bias"]["protect"]["low_end"] == pytest.approx(0.80)

    def test_novelty_budget_max(self):
        """Villalobos=0.6 > BC=0.5 → hybrid novelty budget = 0.6."""
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        brief = compile_hybrid_brief(["basic-channel", "villalobos"])
        assert brief["novelty_budget_default"] == pytest.approx(0.6)


# ── compile_hybrid_brief — tempo_hint rules ─────────────────────────────────


class TestHybridTempoRules:

    def test_overlapping_tempo_ranges_intersect(self):
        """BC 120-130, Villalobos 125-135 → overlap 125-130."""
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        brief = compile_hybrid_brief(["basic-channel", "villalobos"])
        assert brief["tempo_hint"]["min"] == pytest.approx(125)
        assert brief["tempo_hint"]["max"] == pytest.approx(130)
        assert not brief["tempo_hint"].get("disjoint")

    def test_tempo_warning_midpoint_matches_range_center(self):
        """v1.19.1 #2 — the midpoint in the warning text must equal the
        center of the returned tempo range. Pre-v1.19.1 warning used
        `:.0f` (int rounding) while range used exact floats, so BC+Dilla
        produced warning '108 BPM' with range 105-110 centered on 107.5.
        Two rounding conventions; the text and the range disagreed by 0.5.
        """
        from mcp_server.creative_director.hybrid import compile_hybrid_brief
        import re

        brief = compile_hybrid_brief(["basic-channel", "j-dilla"])
        assert brief["tempo_hint"]["disjoint"] is True
        range_center = (brief["tempo_hint"]["min"] + brief["tempo_hint"]["max"]) / 2

        # Extract the midpoint value the warning reported
        warnings = brief["warnings"]
        assert warnings, "expected a tempo warning"
        tempo_warning = next((w for w in warnings if "tempo" in w.lower()), None)
        assert tempo_warning is not None

        # Match the midpoint number in the warning text (may be int or float)
        m = re.search(r"midpoint\s+(\d+(?:\.\d+)?)\s*BPM", tempo_warning)
        assert m, f"couldn't find midpoint value in warning: {tempo_warning}"
        warning_midpoint = float(m.group(1))

        # The warning must agree with the range center within 0.01 BPM
        assert warning_midpoint == pytest.approx(range_center, abs=0.01), (
            f"tempo warning midpoint ({warning_midpoint}) disagrees with "
            f"range center ({range_center})"
        )

    def test_disjoint_tempo_ranges_surface_warning_and_midpoint(self):
        """BC 120-130, Dilla 85-95 → no overlap. Gap midpoint = (95+120)/2 = 107.5.
        Must surface a warning and NOT silently return the midpoint."""
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        brief = compile_hybrid_brief(["basic-channel", "j-dilla"])
        # Range is centered on midpoint ~107.5 but flagged disjoint
        assert brief["tempo_hint"]["disjoint"] is True
        midpoint = (brief["tempo_hint"]["min"] + brief["tempo_hint"]["max"]) / 2
        assert midpoint == pytest.approx(107.5, abs=1.0)
        # Warning must mention tempo
        assert any("tempo" in w.lower() for w in brief["warnings"])


# ── compile_hybrid_brief — multi-packet ─────────────────────────────────────


class TestHybridThreePlusPackets:

    def test_three_packets_compile_without_error(self):
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        brief = compile_hybrid_brief([
            "basic-channel", "j-dilla", "villalobos",
        ])
        assert brief["source_packets"] == ["basic-channel", "j-dilla", "villalobos"]
        assert len(brief["weights"]) == 3
        # Default uniform weights — v1.19.1 rounds to 4 dp so allow 1/3
        # to be represented as 0.3333 without breaking the "uniform" claim.
        assert all(w == pytest.approx(1.0 / 3, abs=1e-3) for w in brief["weights"])

    def test_weights_rounded_to_4dp(self):
        """v1.19.1 #3 — weights in the response should round to 4 decimal
        places, matching the convention target_dimensions already uses.
        Pre-v1.19.1 three-packet uniform weights rendered as
        `0.3333333333333333` — noisy in the brief output."""
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        brief = compile_hybrid_brief([
            "basic-channel", "j-dilla", "villalobos",
        ])
        # Each weight must be representable as a 4-dp float (no trailing
        # repeating decimals in the dict representation)
        for w in brief["weights"]:
            # Round-trip should be a no-op at 4 dp
            assert w == round(w, 4), (
                f"weight {w!r} has more than 4 dp precision"
            )
        # Uniform 3-packet case = 0.3333 exactly
        assert brief["weights"] == [0.3333, 0.3333, 0.3333]

    def test_three_packet_deprioritize_still_intersects_properly(self):
        """With 3 packets, a family is deprioritized only if ALL THREE say so.
        BC / Dilla / Villalobos all deprioritize 'performance' → survives.
        Only BC deprioritizes 'transition' → does not survive."""
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        brief = compile_hybrid_brief([
            "basic-channel", "j-dilla", "villalobos",
        ])
        deprioritize = brief["move_family_bias"]["deprioritize"]
        assert "performance" in deprioritize
        assert "transition" not in deprioritize  # only BC deprioritized it


# ── compile_hybrid_brief — output metadata ──────────────────────────────────


class TestHybridOutputMetadata:

    def test_output_type_is_hybrid(self):
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        brief = compile_hybrid_brief(["basic-channel", "j-dilla"])
        assert brief["type"] == "hybrid"

    def test_source_packets_recorded(self):
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        brief = compile_hybrid_brief(["basic-channel", "j-dilla"])
        assert brief["source_packets"] == ["basic-channel", "j-dilla"]

    def test_hybrid_name_combines_sources(self):
        """Name should mention both sources so the brief is self-describing."""
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        brief = compile_hybrid_brief(["basic-channel", "j-dilla"])
        name = brief["name"]
        assert "Basic Channel" in name
        assert "Dilla" in name

    def test_locked_dimensions_default_empty(self):
        """Hybrids don't lock dimensions — compat field for compliance check."""
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        brief = compile_hybrid_brief(["basic-channel", "j-dilla"])
        assert brief["locked_dimensions"] == []

    def test_warnings_list_always_present(self):
        """Even compatible packets should produce a (possibly-empty) warnings list."""
        from mcp_server.creative_director.hybrid import compile_hybrid_brief

        brief = compile_hybrid_brief(["basic-channel", "villalobos"])
        assert "warnings" in brief
        assert isinstance(brief["warnings"], list)


# ── compile_hybrid_brief — interoperability with compliance check ───────────


class TestHybridInteropWithComplianceCheck:

    def test_hybrid_brief_can_be_passed_to_check_brief_compliance(self):
        """The merged brief should work as input to check_brief_compliance
        without translation. BC + Dilla hybrid avoids 'bright' — a Hi Gain
        boost call should flag."""
        from mcp_server.creative_director.hybrid import compile_hybrid_brief
        from mcp_server.creative_director.compliance import check_brief_compliance

        brief = compile_hybrid_brief(["basic-channel", "j-dilla"])
        result = check_brief_compliance(
            brief=brief,
            tool_name="set_device_parameter",
            tool_args={"parameter_name": "Hi Gain", "value": 3.0},
        )
        assert result["ok"] is False
        # The anti_pattern that fired should reference a brightness-family word
        reason = " ".join(v["detail"].lower() for v in result["violations"])
        assert "bright" in reason or "top" in reason

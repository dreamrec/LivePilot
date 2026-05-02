"""AtlasResolver — v1.25 hybrid knowledge surface.

Three layers of corpus access for the agent:

  Layer A — resolve_anchors():    cohort + role-anchored URIs at brief-build time.
                                  Wraps existing atlas_pack_aware_compose; cheap
                                  (~400 tokens in the brief).
  Layer B — resolve_for_role():   per-role ranked candidates with cohort constraint.
                                  Called by atlas_explore MCP tool during plan design,
                                  and as a fallback when an anchor doesn't fit.
  Layer C — _score():             corpus-deep ranking signals: tag base, signature
                                  technique mood overlap, curated .adg presence,
                                  taste profile, anti-repeat, §1 banned defaults,
                                  pad-opaque-M4L penalty.

Designed to be both invoked from KnowledgePack (brief-build time) AND from the
three new MCP tools (atlas_explore / atlas_audition / atlas_substitute) at
plan-design time. Same ranking logic, same candidate shape.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Constants (memory rules §1, §7 #2) ──────────────────────────────

# §1: Banned as defaults for melodic roles unless mood says "analog".
# Mirrors `_BANNED_DEFAULT_DEVICES` in mcp_server/composer/fast/brief_builder.py
# so the two paths agree.
BANNED_DEFAULT_MELODIC: frozenset[str] = frozenset({"Analog", "Poli", "Drift", "Meld"})

# §1 pad-specific: opaque to the sound-design critic. Stacks with the banned-
# default penalty for pad role on Poli/Meld (intentional — both rules apply).
OPAQUE_M4L_FOR_PAD: frozenset[str] = frozenset({"Poli", "Meld"})

# Brief role → atlas tag candidates (matches fast/brief_builder.py _ROLE_TAGS).
_ROLE_TAGS: dict[str, tuple[str, ...]] = {
    "kick":       ("kick", "drum", "808"),
    "snare":      ("snare", "clap", "drum"),
    "hat":        ("hihat", "hi-hat", "hat", "cymbal"),
    "perc":       ("perc", "percussion", "drum"),
    "clap":       ("clap", "snare"),
    "bass":       ("bass", "sub_bass", "sub"),
    "pad":        ("pad", "texture", "atmos", "ambient"),
    "lead":       ("lead", "synth_lead", "pluck"),
    "atmos":      ("atmos", "ambient", "drone", "texture"),
    "vocal_chop": ("vocal", "vox", "voice"),
    "fx":         ("fx", "effect", "transition"),
    "spectral":   ("spectral", "stretch", "freeze"),
}

_MELODIC_ROLES: frozenset[str] = frozenset({"bass", "lead", "pad", "atmos", "vocal_chop"})

# pack_aware_compose's coarse roles → brief's finer roles.
# Used in resolve_anchors to spread one cohort pick across multiple fine roles.
_COARSE_TO_FINE_ROLES: dict[str, tuple[str, ...]] = {
    "rhythmic-driver":      ("kick", "snare", "hat"),
    "bass":                 ("bass",),
    "melodic":              ("lead", "vocal_chop"),
    "harmonic-foundation":  ("pad",),
    "wash":                 ("atmos",),
    "fx-bus":               ("fx",),
    "spectral-processing":  ("spectral",),
}


# ── Dataclasses ─────────────────────────────────────────────────────


@dataclass
class AtlasCandidate:
    """A single device/preset candidate with full reasoning trail."""
    uri: str
    name: str
    source: str = "atlas"  # "atlas" | "extension_atlas:packs" | "extension_atlas:m4l-devices" | "browser" | "pack_aware_compose"
    score: float = 0.0
    character_tags: list[str] = field(default_factory=list)
    signature_techniques: list[str] = field(default_factory=list)
    in_pack: Optional[str] = None
    has_curated_adg: bool = False
    reasoning: str = ""


@dataclass
class AtlasAnchors:
    """Brief-level pre-resolution. Carried in KnowledgePack output. ~400 tokens."""
    primary_pack: Optional[str] = None
    pack_cohort: list[str] = field(default_factory=list)
    anchor_producers: list[str] = field(default_factory=list)
    anchor_genres: list[str] = field(default_factory=list)
    primary_aesthetic: str = ""
    vocab_tags: list[str] = field(default_factory=list)
    techniques_in_play: list[str] = field(default_factory=list)
    cohort_uris: dict[str, str] = field(default_factory=dict)  # role → URI/preset slug
    reasoning: str = ""


# ── Resolver ────────────────────────────────────────────────────────


class AtlasResolver:
    """Layer-aware atlas knowledge resolver for the v1.25 hybrid surface."""

    def __init__(
        self,
        *,
        atlas: Any,
        ableton: Any = None,
        taste_profile: Optional[dict] = None,
        recent_uris: Optional[set[str]] = None,
    ):
        self._atlas = atlas
        self._ableton = ableton
        self._taste_profile: dict = dict(taste_profile or {})
        self._recent_uris: set[str] = set(recent_uris or set())

    # ── Layer A — anchors ───────────────────────────────────────

    def resolve_anchors(
        self,
        *,
        brief_text: str,
        genre: str = "",
        mood: str = "",
        artist_refs: Optional[list[str]] = None,
    ) -> AtlasAnchors:
        """Pre-resolve brief-level anchors via atlas_pack_aware_compose.

        Wraps the existing v1.23 cohort tool (which already does coherent
        pack/producer cluster selection across artist + genre vocabularies),
        then maps its 7 coarse roles onto the brief's finer 8 roles via
        _COARSE_TO_FINE_ROLES. Best-effort: if pack_aware_compose errors or
        is unavailable, returns an empty AtlasAnchors (anchor_producers,
        cohort_uris all empty) rather than raising.
        """
        artist_refs = list(artist_refs or [])
        try:
            from ...atlas.pack_aware_compose import pack_aware_compose
        except Exception as exc:  # import error — corpus not installed
            logger.debug("resolve_anchors: import pack_aware_compose failed: %s", exc)
            return AtlasAnchors(reasoning=f"pack_aware_compose unavailable ({exc})")

        try:
            result = pack_aware_compose(
                aesthetic_brief=brief_text or "",
                target_bpm=None,
                target_scale="",
                track_count=8,
                pack_diversity="coherent",
            )
        except Exception as exc:
            logger.debug("resolve_anchors: pack_aware_compose raised: %s", exc)
            return AtlasAnchors(reasoning=f"pack_aware_compose raised ({exc})")

        if not isinstance(result, dict) or result.get("error") or result.get("status") == "error":
            err = (result or {}).get("error") if isinstance(result, dict) else "no result"
            return AtlasAnchors(reasoning=f"pack_aware_compose error: {err}")

        ba = result.get("brief_analysis") or {}
        cohort = list(ba.get("pack_cohort") or result.get("pack_cohort") or [])
        cohort_uris = self._map_pack_aware_roles(result.get("track_proposal") or [])
        techniques = self._extract_techniques_for_packs(cohort)

        # vocab_tags = anchor producers + genres + mood + primary aesthetic.
        # De-dup while preserving order so the highest-priority tag stays first.
        vocab: list[str] = []
        seen: set[str] = set()
        for v in (
            [ba.get("primary_aesthetic", "") or ""]
            + list(ba.get("secondary_aesthetics") or [])
            + artist_refs
            + ([mood] if mood else [])
        ):
            v = (v or "").strip()
            if v and v.lower() not in seen:
                seen.add(v.lower())
                vocab.append(v)

        return AtlasAnchors(
            primary_pack=cohort[0] if cohort else None,
            pack_cohort=cohort,
            anchor_producers=list(ba.get("anchor_producers") or []),
            anchor_genres=list(ba.get("anchor_genres") or []),
            primary_aesthetic=ba.get("primary_aesthetic") or "",
            vocab_tags=vocab,
            techniques_in_play=techniques,
            cohort_uris=cohort_uris,
            reasoning=self._anchors_reasoning(ba, cohort, mood),
        )

    @staticmethod
    def _map_pack_aware_roles(track_proposal: list[dict]) -> dict[str, str]:
        """pack_aware_compose's coarse roles → brief's fine roles.

        Track proposal entries carry `role` (coarse) and `preset` (slug
        "pack/preset-name"). Spread the preset slug across the fine roles
        the coarse role covers — the apply pass resolves the slug to a
        runtime URI via search_browser.
        """
        cohort_uris: dict[str, str] = {}
        for tp in track_proposal:
            coarse = tp.get("role") or ""
            preset = (tp.get("preset") or "").strip()
            if not preset:
                continue
            for fine in _COARSE_TO_FINE_ROLES.get(coarse, ()):
                cohort_uris.setdefault(fine, preset)
        return cohort_uris

    @staticmethod
    def _extract_techniques_for_packs(cohort: list[str]) -> list[str]:
        """Pull signature_techniques cross-referenced for cohort packs.

        v1.25 skeleton — returns []. Wired in v1.25.x once
        device_techniques_index.json reverse-lookup is in place.
        """
        return []

    @staticmethod
    def _anchors_reasoning(brief_analysis: dict, cohort: list[str], mood: str) -> str:
        bits: list[str] = []
        aesthetic = brief_analysis.get("primary_aesthetic")
        if aesthetic:
            bits.append(f"primary aesthetic '{aesthetic}'")
        if cohort:
            bits.append(f"cohort: {', '.join(cohort[:3])}")
        if mood:
            bits.append(f"mood '{mood}'")
        if not bits:
            return "Default cohort (no aesthetic anchors detected in brief)."
        return "Anchors derived from " + "; ".join(bits) + "."

    # ── Layer B — per-role candidates ───────────────────────────

    def resolve_for_role(
        self,
        *,
        role: str,
        genre: str = "",
        mood: str = "",
        artist_refs: Optional[list[str]] = None,
        avoid: Optional[list[str]] = None,
        cohort_constraint: Optional[list[str]] = None,
        excluded_uris: Optional[set[str]] = None,
        n: int = 5,
    ) -> list[AtlasCandidate]:
        """Resolve N ranked candidates for a single role.

        Uses atlas tag indexes as primary. Deeper sources (extension_atlas,
        search_browser) are deferred to v1.25.x once the surface is proven.

        Returns list[AtlasCandidate] sorted by score descending, length <= n.
        Empty list when atlas is None or no candidates pass filters.
        """
        if self._atlas is None:
            return []

        artist_refs = list(artist_refs or [])
        avoid_list = list(avoid or [])
        excluded = set(excluded_uris or set())
        cohort_set = set(cohort_constraint or [])

        role_lower = (role or "").lower()
        tags = _ROLE_TAGS.get(role_lower, (role_lower,))

        # ── Source 1: factory atlas tag index ───────────────────────
        seen_uris: set[str] = set()
        candidates: list[tuple[dict, str]] = []  # (device, source_label)
        by_tag = getattr(self._atlas, "_by_tag", {}) or {}
        for tag in tags:
            for dev in by_tag.get(str(tag).lower(), []):
                uri = dev.get("uri") or ""
                if not uri or uri in seen_uris or uri in excluded:
                    continue
                if cohort_set and dev.get("pack") not in cohort_set:
                    continue
                seen_uris.add(uri)
                candidates.append((dev, "atlas"))

        # ── Source 2: extension_atlas overlays (user corpus + packs + m4l-devices + demos) ──
        # Per user mandate: full-mode resolve_for_role MUST union with the overlay
        # corpus. Producer-curated rack instruments (808 Trap Selector Rack from
        # Trap Drums by Sound Oracle, Harmonic Drone Generator from Drone Lab,
        # user-scanned .amxd library, etc.) live in overlays only, never in the
        # factory tag index. Best-effort: import failure leaves overlay results
        # empty rather than raising.
        overlay_devs = self._gather_from_overlays(
            role=role_lower,
            tags=tags,
            cohort_set=cohort_set,
            excluded=excluded,
            seen_uris=seen_uris,
        )
        for dev in overlay_devs:
            candidates.append((dev, dev.get("_overlay_source") or "extension_atlas"))

        scored: list[tuple[float, AtlasCandidate]] = []
        for dev, source_label in candidates:
            score, reasoning = self._score(
                dev,
                role=role_lower,
                genre=genre,
                mood=mood,
                artist_refs=artist_refs,
                avoid=avoid_list,
            )
            # +0.15 for demo_project entries — ground-truth role→URI mappings
            # from analyzed Ableton-shipped .als demos. Per user mandate these
            # are the highest-confidence per-role anchors.
            if source_label == "extension_atlas:demo_project":
                score += 0.15
                reasoning = f"{reasoning}; demo_project ground-truth (+0.15)"
            scored.append((score, self._to_candidate(dev, score, reasoning, source=source_label)))

        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored[:n]]

    def _gather_from_overlays(
        self,
        *,
        role: str,
        tags: tuple[str, ...],
        cohort_set: set[str],
        excluded: set[str],
        seen_uris: set[str],
    ) -> list[dict]:
        """Pull role-matching candidates from extension_atlas overlay namespaces.

        Searches THREE overlay surfaces:
          1. `packs` namespace, entity_type="demo_project" — ground-truth role→URI
             mappings extracted from analyzed factory pack .als demos. Highest
             confidence per-role anchor source. Tagged "extension_atlas:demo_project".
          2. `packs` / `m4l-devices` / `elektron` / `user.*` namespaces, all
             entity_types — surfaces curated rack instruments and user-scanned
             devices not in the factory tag index. Tagged "extension_atlas".
          3. Per-tag substring search per role (e.g., "808" tag for kick/bass)
             so producer-curated instruments with role-bearing tags are surfaced.

        Returns list[dict] in atlas-candidate-shape (uri, name, character_tags,
        signature_techniques, pack=namespace, _overlay_source).
        """
        try:
            from ...atlas.overlays import get_overlay_index
        except Exception as exc:  # overlay backend unavailable
            logger.debug("_gather_from_overlays: overlay import failed: %s", exc)
            return []

        try:
            idx = get_overlay_index()
        except Exception as exc:
            logger.debug("_gather_from_overlays: get_overlay_index failed: %s", exc)
            return []

        results: list[dict] = []

        # Pass A — demo_project ground truth (limit 10 per tag, dedup downstream).
        for tag in tags:
            try:
                matches = idx.search(
                    str(tag).lower(),
                    namespace="packs",
                    entity_type="demo_project",
                    limit=10,
                )
            except Exception:
                continue
            for entry in matches:
                dev = self._overlay_entry_to_device(entry, source="extension_atlas:demo_project")
                if not dev:
                    continue
                uri = dev.get("uri") or ""
                if uri and uri in seen_uris or uri in excluded:
                    continue
                if cohort_set and dev.get("pack") not in cohort_set:
                    continue
                if uri:
                    seen_uris.add(uri)
                results.append(dev)

        # Pass B — full overlay search across all namespaces and entity_types.
        for tag in tags:
            try:
                matches = idx.search(str(tag).lower(), limit=10)
            except Exception:
                continue
            for entry in matches:
                # Skip duplicate hits already covered by Pass A.
                if getattr(entry, "entity_type", "") == "demo_project":
                    continue
                dev = self._overlay_entry_to_device(entry, source="extension_atlas")
                if not dev:
                    continue
                uri = dev.get("uri") or ""
                if uri and uri in seen_uris or uri in excluded:
                    continue
                if cohort_set and dev.get("pack") not in cohort_set:
                    continue
                if uri:
                    seen_uris.add(uri)
                results.append(dev)

        return results

    @staticmethod
    def _overlay_entry_to_device(entry: Any, *, source: str) -> Optional[dict]:
        """Map an OverlayEntry to the atlas-candidate dict shape.

        Overlay entries don't carry a load-able URI in the same shape as the
        factory atlas; we synthesize one as `overlay://<namespace>/<entity_id>`
        so the agent can still call extension_atlas_get(namespace, entity_id)
        to resolve the actual loadable resource. The character_tags field
        carries the overlay's tags so _score's mood-overlap heuristic still
        fires.
        """
        try:
            namespace = getattr(entry, "namespace", "") or ""
            entity_id = getattr(entry, "entity_id", "") or ""
            if not namespace or not entity_id:
                return None
            return {
                "uri": f"overlay://{namespace}/{entity_id}",
                "name": getattr(entry, "name", "") or entity_id,
                "character_tags": list(getattr(entry, "tags", []) or []),
                "signature_techniques": [],
                "pack": namespace,
                "has_curated_adg": False,
                "_overlay_source": source,
                "_overlay_namespace": namespace,
                "_overlay_entity_id": entity_id,
            }
        except Exception:
            return None

    # ── Layer C — ranking ───────────────────────────────────────

    def _score(
        self,
        dev: dict,
        *,
        role: str,
        genre: str,
        mood: str,
        artist_refs: list[str],
        avoid: list[str],
    ) -> tuple[float, str]:
        """Compute (score in [0, 1], reasoning string) for one candidate."""
        score = 0.5  # baseline tag-match
        reasons: list[str] = ["tag match"]

        name = dev.get("name") or ""
        sig_techs = list(dev.get("signature_techniques") or [])

        mood_lower = (mood or "").lower()
        genre_lower = (genre or "").lower()

        # +0.20 signature_technique mood overlap (token-level)
        if sig_techs and mood_lower:
            mood_tokens = [tok for tok in mood_lower.split() if len(tok) > 3]
            for tech in sig_techs:
                tech_lower = str(tech).lower()
                if any(tok in tech_lower for tok in mood_tokens):
                    score += 0.20
                    reasons.append(f"signature_technique '{tech}' matches mood")
                    break

        # +0.10 has curated .adg sidecar
        if self._has_curated_adg(dev):
            score += 0.10
            reasons.append("curated .adg sidecar")

        # +0.10 recent positive preference
        if name and self._taste_profile.get(name, {}).get("score", 0) > 0:
            score += 0.10
            reasons.append("recent positive preference")

        # +0.10/+0.05 genre primary/secondary
        if genre_lower:
            primary, secondary = self._device_genres(dev)
            if any(genre_lower in g for g in primary):
                score += 0.10
                reasons.append(f"genre primary '{genre}'")
            elif any(genre_lower in g for g in secondary):
                score += 0.05
                reasons.append(f"genre secondary '{genre}'")

        # −0.50 §1 banned default for melodic role, mood not "analog"
        if role in _MELODIC_ROLES and name in BANNED_DEFAULT_MELODIC:
            if "analog" not in mood_lower:
                score -= 0.50
                reasons.append(f"§1 banned default '{name}' (mood not 'analog')")

        # −0.30 pad role with opaque M4L
        if role == "pad" and name in OPAQUE_M4L_FOR_PAD:
            score -= 0.30
            reasons.append(f"opaque M4L pad '{name}' (sound-design critic blind)")

        # −0.15 anti-repeat (recent_uris)
        uri = dev.get("uri") or ""
        if uri and uri in self._recent_uris:
            score -= 0.15
            reasons.append("recently used (§7 #2 anti-repeat)")

        # −0.30 caller-supplied avoid-list
        if name in avoid:
            score -= 0.30
            reasons.append("on caller-supplied avoid list")

        score = max(0.0, min(1.0, score))
        return score, "; ".join(reasons)

    @staticmethod
    def _device_genres(dev: dict) -> tuple[list[str], list[str]]:
        """Return (primary, secondary) genre lists, lowercased, dup-tolerant."""
        primary: list[str] = []
        secondary: list[str] = []
        for key in ("genre_affinity", "genres"):
            container = dev.get(key) or {}
            if not isinstance(container, dict):
                continue
            for g in container.get("primary", []) or []:
                primary.append(str(g).lower())
            for g in container.get("secondary", []) or []:
                secondary.append(str(g).lower())
        return primary, secondary

    @staticmethod
    def _has_curated_adg(dev: dict) -> bool:
        """Heuristic: has curated .adg if explicit flag, .adg URI, or /adg/ path hint."""
        if dev.get("has_curated_adg"):
            return True
        uri = (dev.get("uri") or "").lower()
        if uri.endswith(".adg") or "/adg/" in uri:
            return True
        return False

    @staticmethod
    def _to_candidate(dev: dict, score: float, reasoning: str, *, source: str) -> AtlasCandidate:
        char_tags = list(dev.get("character_tags") or dev.get("tags") or [])
        return AtlasCandidate(
            uri=dev.get("uri") or "",
            name=dev.get("name") or "",
            source=source,
            score=score,
            character_tags=char_tags,
            signature_techniques=list(dev.get("signature_techniques") or []),
            in_pack=dev.get("pack"),
            has_curated_adg=AtlasResolver._has_curated_adg(dev),
            reasoning=reasoning,
        )

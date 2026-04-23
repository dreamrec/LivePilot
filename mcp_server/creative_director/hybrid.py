"""Hybrid concept packet compilation (v1.19 Item B).

When the user says "Basic Channel meets Dilla swing" or
"Villalobos but sparse like Gas", the director needs to merge
two (or more) concept packets into a single brief. Pre-v1.19
this was LLM ad-hoc reasoning with no guarantees about
contradiction handling.

``compile_hybrid_brief(packet_ids, weights=None)`` loads the
named packets from
``livepilot/skills/livepilot-core/references/concepts/`` and
merges them per the rules in
``docs/plans/v1.19-structural-plan.md §3``.

Design invariants:

1. **UNION** the descriptive fields (sonic_identity, avoid,
   reach_for.*, *_idioms) — hybrids describe the envelope of
   BOTH sources, not the intersection.
2. **INTERSECTION** the deprioritization fields
   (dimensions_deprioritized, move_family_bias.deprioritize) —
   a hybrid only deprioritizes something if BOTH sources agree
   it should be deprioritized. Otherwise the other packet is
   asking for it and the hybrid must honor that.
3. **INTERSECTION (with UNION fallback + warning)** for
   move_family_bias.favor — hybrids focus where both packets
   agree when possible; when they don't overlap at all, fall
   back to UNION but warn (the hybrid spans more families
   than either source intends).
4. **MAX** for stricter-wins fields (protect floors,
   novelty_budget_default).
5. **WEIGHTED AVERAGE** for continuous blends
   (target_dimensions weights).
6. **NEAREST-OVERLAP** for tempo_hint — intersect when ranges
   overlap; warn and use midpoint when they don't.
7. **Surface ambiguity** — all warnings go on the ``warnings``
   list so the caller (director) can read them back to the
   user.

Output is a dict that is structurally compatible with
:func:`mcp_server.creative_director.compliance.check_brief_compliance`:
the merged ``avoid`` list is also exposed as ``anti_patterns``,
and ``locked_dimensions`` defaults to ``[]`` (hybrids don't lock
dimensions by default — that's a per-turn choice).
"""

from __future__ import annotations

import logging
import pathlib
from typing import Iterable, Optional

import yaml

logger = logging.getLogger(__name__)


# Resolve the concepts root relative to this file. Layout:
#   mcp_server/creative_director/hybrid.py
#   livepilot/skills/livepilot-core/references/concepts/
# Three parents up from this file → repo root.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_CONCEPTS_ROOT = (
    _REPO_ROOT / "livepilot" / "skills" / "livepilot-core"
    / "references" / "concepts"
)


# ── Packet loader ────────────────────────────────────────────────────────────


def _normalize(s: str) -> str:
    """Lowercase, hyphenate whitespace and underscores for lookup."""
    return s.strip().lower().replace("_", "-").replace(" ", "-")


def load_packet(packet_id: str) -> Optional[dict]:
    """Load a concept packet by filename stem, alias, or packet.id.

    Resolution order (first hit wins):
      1. Normalize the given id (lowercase, underscores → hyphens).
      2. Try ``artists/<norm>.yaml`` then ``genres/<norm>.yaml``.
      3. If still not found, scan all packets and match on ``id``
         or any alias (normalized).
      4. Return None on miss.
    """
    norm = _normalize(packet_id)

    for subdir in ("artists", "genres"):
        candidate = _CONCEPTS_ROOT / subdir / f"{norm}.yaml"
        if candidate.exists():
            try:
                return yaml.safe_load(candidate.read_text())
            except Exception as exc:
                logger.debug("load_packet parse failed for %s: %s", candidate, exc)
                return None

    # Fallback: scan for alias / id match
    for subdir in ("artists", "genres"):
        subpath = _CONCEPTS_ROOT / subdir
        if not subpath.is_dir():
            continue
        for p in sorted(subpath.glob("*.yaml")):
            try:
                d = yaml.safe_load(p.read_text())
            except Exception as exc:
                logger.debug("load_packet scan-parse failed for %s: %s", p, exc)
                continue
            if not isinstance(d, dict):
                continue
            if d.get("id") == packet_id:
                return d
            aliases = [_normalize(a) for a in (d.get("aliases") or []) if isinstance(a, str)]
            if norm in aliases:
                return d

    return None


# ── Merge helpers ────────────────────────────────────────────────────────────


def _union_preserve_order(lists: Iterable[Iterable[str]]) -> list[str]:
    seen: set = set()
    out: list[str] = []
    for lst in lists:
        for item in (lst or []):
            if item not in seen:
                seen.add(item)
                out.append(item)
    return out


def _intersection_preserve_order(
    lists: list[list[str]], reference_order: list[str],
) -> list[str]:
    """Intersect across all lists; ordering follows ``reference_order``
    (typically the first packet's list)."""
    if not lists:
        return []
    sets = [set(lst or []) for lst in lists]
    intersection = sets[0]
    for s in sets[1:]:
        intersection = intersection & s
    return [item for item in (reference_order or []) if item in intersection]


# ── Core compile function (packet-level, no disk I/O) ───────────────────────


def _compile_from_packets(
    packets: list[dict],
    packet_ids: list[str],
    weights: Optional[list[float]] = None,
) -> dict:
    """Compile a hybrid brief from already-loaded packet dicts.

    Public callers should use :func:`compile_hybrid_brief`. This split
    exists so tests can inject synthetic packets (e.g., to force an
    empty favor-intersection and exercise the UNION fallback).
    """
    if len(packets) < 2:
        raise ValueError("Hybrid requires at least 2 packets")
    if weights is not None and len(weights) != len(packets):
        raise ValueError(
            f"weights length ({len(weights)}) must match packets "
            f"length ({len(packets)})"
        )

    if weights is None:
        weights = [1.0 / len(packets)] * len(packets)
    else:
        total = sum(weights) or 1.0
        weights = [w / total for w in weights]

    warnings: list[str] = []

    # ── UNION fields ─────────────────────────────────────────────────────
    sonic_identity = _union_preserve_order(
        p.get("sonic_identity") or [] for p in packets
    )
    avoid = _union_preserve_order(p.get("avoid") or [] for p in packets)
    rhythm_idioms = _union_preserve_order(p.get("rhythm_idioms") or [] for p in packets)
    harmony_idioms = _union_preserve_order(p.get("harmony_idioms") or [] for p in packets)
    arrangement_idioms = _union_preserve_order(
        p.get("arrangement_idioms") or [] for p in packets
    )
    texture_idioms = _union_preserve_order(p.get("texture_idioms") or [] for p in packets)
    sample_roles = _union_preserve_order(p.get("sample_roles") or [] for p in packets)
    dimensions_in_scope = _union_preserve_order(
        p.get("dimensions_in_scope") or [] for p in packets
    )

    reach_for = {
        "instruments": _union_preserve_order(
            (p.get("reach_for") or {}).get("instruments") or [] for p in packets
        ),
        "effects": _union_preserve_order(
            (p.get("reach_for") or {}).get("effects") or [] for p in packets
        ),
        "packs": _union_preserve_order(
            (p.get("reach_for") or {}).get("packs") or [] for p in packets
        ),
        "utilities": _union_preserve_order(
            (p.get("reach_for") or {}).get("utilities") or [] for p in packets
        ),
    }

    # ── INTERSECTION fields (safety defaults — be cautious) ─────────────
    # deprioritize only if ALL packets agree → a hybrid with one packet
    # asking for rhythmic must NOT deprioritize rhythmic just because the
    # other packet's aesthetic does.
    dimensions_deprioritized = _intersection_preserve_order(
        [p.get("dimensions_deprioritized") or [] for p in packets],
        packets[0].get("dimensions_deprioritized") or [],
    )

    deprioritize = _intersection_preserve_order(
        [(p.get("move_family_bias") or {}).get("deprioritize") or []
         for p in packets],
        (packets[0].get("move_family_bias") or {}).get("deprioritize") or [],
    )

    # ── favor: INTERSECTION preferred, UNION fallback with warning ──────
    favor_lists = [
        (p.get("move_family_bias") or {}).get("favor") or [] for p in packets
    ]
    favor_intersection = _intersection_preserve_order(
        favor_lists, favor_lists[0],
    )
    if favor_intersection:
        favor = favor_intersection
    else:
        favor = _union_preserve_order(favor_lists)
        warnings.append(
            "move_family_bias.favor intersection was empty — falling back "
            "to UNION. Hybrid plans may span more families than either "
            "source packet intends; prioritize explicit user framing."
        )

    # ── Numeric rules ───────────────────────────────────────────────────
    # target_dimensions: WEIGHTED AVERAGE
    all_dim_keys: set = set()
    for p in packets:
        td = (p.get("evaluation_bias") or {}).get("target_dimensions") or {}
        all_dim_keys.update(td.keys())
    target_dimensions: dict[str, float] = {}
    for dim in sorted(all_dim_keys):
        accum = 0.0
        for w, p in zip(weights, packets):
            td = (p.get("evaluation_bias") or {}).get("target_dimensions") or {}
            val = td.get(dim, 0.0)
            try:
                accum += float(w) * float(val)
            except (TypeError, ValueError):
                continue
        if accum > 0:
            target_dimensions[dim] = round(accum, 4)

    # protect: MAX per dimension (stricter wins)
    all_protect_keys: set = set()
    for p in packets:
        pr = (p.get("evaluation_bias") or {}).get("protect") or {}
        all_protect_keys.update(pr.keys())
    protect: dict[str, float] = {}
    for dim in sorted(all_protect_keys):
        values = []
        for p in packets:
            pr = (p.get("evaluation_bias") or {}).get("protect") or {}
            val = pr.get(dim, 0.0)
            try:
                values.append(float(val))
            except (TypeError, ValueError):
                continue
        if values:
            protect[dim] = max(values)

    # novelty_budget_default: MAX (hybrids lean exploratory)
    novelty_values: list[float] = []
    for p in packets:
        nb = p.get("novelty_budget_default")
        if nb is None:
            continue
        try:
            novelty_values.append(float(nb))
        except (TypeError, ValueError):
            continue
    novelty_budget = max(novelty_values) if novelty_values else 0.5

    # ── tempo_hint: NEAREST-OVERLAP ─────────────────────────────────────
    tempo_ranges: list[tuple[float, float, str]] = []
    for p in packets:
        th = p.get("tempo_hint") or {}
        lo, hi = th.get("min"), th.get("max")
        if lo is None or hi is None:
            continue
        try:
            tempo_ranges.append((float(lo), float(hi), p.get("name", "")))
        except (TypeError, ValueError):
            continue

    tempo_hint: Optional[dict]
    if not tempo_ranges:
        tempo_hint = None
    elif len(tempo_ranges) == 1:
        lo, hi, _ = tempo_ranges[0]
        tempo_hint = {"min": lo, "max": hi, "time_signature": "4/4"}
    else:
        overlap_lo = max(r[0] for r in tempo_ranges)
        overlap_hi = min(r[1] for r in tempo_ranges)
        if overlap_lo <= overlap_hi:
            tempo_hint = {
                "min": overlap_lo, "max": overlap_hi,
                "time_signature": "4/4",
            }
        else:
            # Disjoint ranges — compute gap midpoint, surface warning.
            # The gap is between the highest range-max and the lowest
            # range-min that exceeds it. For 2 ranges this is
            # (max of all his, min of all los). For 3+ ranges this still
            # reads as "the gap in the middle of the sorted range set".
            sorted_ranges = sorted(tempo_ranges, key=lambda r: r[0])
            gap_lo = max(r[1] for r in sorted_ranges if r[0] < sorted_ranges[-1][0])
            gap_hi = sorted_ranges[-1][0]
            midpoint = (gap_lo + gap_hi) / 2.0
            tempo_hint = {
                "min": midpoint - 2.5,
                "max": midpoint + 2.5,
                "time_signature": "4/4",
                "disjoint": True,
            }
            range_desc = "; ".join(
                f"{name or 'packet'} {lo:.0f}-{hi:.0f}"
                for lo, hi, name in tempo_ranges
            )
            warnings.append(
                f"Tempo ranges don't overlap ({range_desc}) — defaulting "
                f"to midpoint {midpoint:.0f} BPM. Specify which anchor "
                f"you want or pick a single packet."
            )

    # ── Output ───────────────────────────────────────────────────────────
    names = [p.get("name") or pid for p, pid in zip(packets, packet_ids)]
    hybrid_name = " × ".join(names)

    return {
        "type": "hybrid",
        "source_packets": list(packet_ids),
        "weights": list(weights),
        "name": hybrid_name,
        "sonic_identity": sonic_identity,
        "reach_for": reach_for,
        "avoid": avoid,
        # Alias for compatibility with check_brief_compliance, which reads
        # "anti_patterns". The semantics are identical — "avoid" at the
        # packet layer, "anti_patterns" at the brief layer.
        "anti_patterns": list(avoid),
        "rhythm_idioms": rhythm_idioms,
        "harmony_idioms": harmony_idioms,
        "arrangement_idioms": arrangement_idioms,
        "texture_idioms": texture_idioms,
        "sample_roles": sample_roles,
        "evaluation_bias": {
            "target_dimensions": target_dimensions,
            "protect": protect,
        },
        "move_family_bias": {
            "favor": favor,
            "deprioritize": deprioritize,
        },
        "dimensions_in_scope": dimensions_in_scope,
        "dimensions_deprioritized": dimensions_deprioritized,
        # Hybrids do not lock dimensions by default — locking is a per-turn
        # user choice (e.g., "don't touch structure"). Included here for
        # compat with check_brief_compliance which reads this field.
        "locked_dimensions": [],
        "novelty_budget_default": novelty_budget,
        "tempo_hint": tempo_hint,
        "warnings": warnings,
    }


# ── Public API ───────────────────────────────────────────────────────────────


def compile_hybrid_brief(
    packet_ids: list[str],
    weights: Optional[list[float]] = None,
) -> dict:
    """Merge N concept packets into a single hybrid brief.

    packet_ids: filename stems (``'basic-channel'``), aliases
      (``'dilla'``), or packet ``id`` values (``'dub_techno__basic_channel'``).
      At least 2 required.
    weights: optional per-packet weighting for the target_dimensions
      weighted-average step. If None, uniform weights are used.
      Must match ``packet_ids`` length when provided. Normalized to
      sum to 1.0 internally.

    Raises:
      ValueError: on fewer than 2 packets, an unresolvable packet id,
        or a weights-length mismatch.

    Returns:
      A dict structurally compatible with the packet schema plus:
        - ``type``: always ``"hybrid"``
        - ``source_packets``: ``packet_ids`` echoed back
        - ``weights``: normalized weights
        - ``name``: ``"Packet A × Packet B"`` for user-facing display
        - ``anti_patterns``: alias of ``avoid`` (compat with
          ``check_brief_compliance``)
        - ``locked_dimensions``: empty by default (hybrids don't lock)
        - ``warnings``: list of human-readable ambiguity notes (tempo
          disjunction, empty favor intersection fallback, etc.). Empty
          when all merge rules resolved cleanly.
    """
    packets: list[dict] = []
    missing: list[str] = []
    for pid in packet_ids:
        p = load_packet(pid)
        if p is None:
            missing.append(pid)
        else:
            packets.append(p)

    if missing:
        raise ValueError(f"Packets not found: {missing}")

    return _compile_from_packets(packets, list(packet_ids), weights=weights)

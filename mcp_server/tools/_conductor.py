"""Conductor — intelligent request routing to specialized engines.

Analyzes a natural-language production request and determines which engines
should handle it, in what order, with what priority. This is the "brain"
that connects all the specialist engines into a coherent workflow.

Zero external dependencies beyond stdlib.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Optional


# ── Engine Registry ──────────────────────────────────────────────────

@dataclass
class EngineRoute:
    """A routing decision for a single engine."""
    engine: str
    priority: int  # 1=primary, 2=secondary, 3=supporting
    reason: str
    entry_tool: str  # which MCP tool to call first
    follow_up_tools: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ConductorPlan:
    """Full routing plan for a production request."""
    request: str
    request_type: str  # "mix", "composition", "sound_design", "transition", etc.
    routes: list[EngineRoute] = field(default_factory=list)
    capability_requirements: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    budget: Optional[dict] = None

    # V2 additions
    semantic_moves: list[dict] = field(default_factory=list)
    workflow_mode: str = "guided_workflow"  # quick_fix | guided_workflow | agentic_loop | creative_search | performance_safe
    use_session_kernel: bool = True
    experiment_recommended: bool = False

    def to_dict(self) -> dict:
        result = {
            "request": self.request,
            "request_type": self.request_type,
            "routes": [r.to_dict() for r in self.routes],
            "engine_count": len(self.routes),
            "primary_engine": self.routes[0].engine if self.routes else None,
            "capability_requirements": self.capability_requirements,
            "notes": self.notes,
            "semantic_moves": self.semantic_moves,
            "workflow_mode": self.workflow_mode,
            "use_session_kernel": self.use_session_kernel,
            "experiment_recommended": self.experiment_recommended,
        }
        if self.budget is not None:
            result["budget"] = self.budget
        return result


# ── Request Classification ───────────────────────────────────────────

# Keyword → (engine, request_type, entry_tool, follow_up_tools)
_ROUTING_PATTERNS: list[tuple[str, str, str, str, list[str]]] = [
    # Mix requests
    (r"clean|mud|muddy|low.?mid|eq|equaliz", "mix_engine", "mix", "analyze_mix", ["plan_mix_move", "evaluate_mix_move"]),
    (r"punch|punchy|transient|dynamics|compress", "mix_engine", "mix", "analyze_mix", ["plan_mix_move"]),
    (r"wide|wider|width|stereo|narrow|mono.?compat", "mix_engine", "mix", "analyze_mix", ["plan_mix_move"]),
    (r"glue|cohes|bus.?comp|mix.?bus", "mix_engine", "mix", "analyze_mix", ["plan_mix_move"]),
    (r"balance|level|volume.?balanc|gain.?stag", "mix_engine", "mix", "analyze_mix", ["plan_mix_move"]),
    (r"headroom|clip|peak|limit", "mix_engine", "mix", "analyze_mix", ["plan_mix_move"]),
    (r"depth|dry|wet|reverb.?mix|send", "mix_engine", "mix", "analyze_mix", ["plan_mix_move"]),
    (r"mask|frequency.?collis|overlap", "mix_engine", "mix", "get_masking_report", ["plan_mix_move"]),

    # Composition requests
    (r"arrange|arrangement|song.?structure|loop.?to.?song", "composition", "composition", "plan_arrangement", ["analyze_composition"]),
    (r"section|verse|chorus|drop|intro|outro|bridge|breakdown", "composition", "composition", "analyze_composition", ["get_section_graph"]),
    (r"phrase|motif|pattern|repetit|variation", "composition", "composition", "analyze_composition", ["get_motif_graph"]),
    (r"tension|energy.?arc|emotional|build.?up", "composition", "composition", "get_emotional_arc", ["analyze_composition"]),
    (r"form|structure|reorder|expand|compress|split|insert", "composition", "composition", "transform_section", ["analyze_composition"]),

    # Sound design requests
    (r"synth|patch|oscillat|timbre|timbral|wavetable|operator", "sound_design", "sound_design", "analyze_sound_design", ["plan_sound_design_move"]),
    (r"haunted|lush|aggressive|warm.?pad|fat.?bass|bright.?lead", "sound_design", "sound_design", "analyze_sound_design", ["plan_sound_design_move"]),
    (r"modulation|lfo|movement|evolv|texture", "sound_design", "sound_design", "get_patch_model", ["analyze_sound_design"]),
    (r"layer|sub.?layer|transient.?layer|body", "sound_design", "sound_design", "analyze_sound_design", ["plan_sound_design_move"]),

    # Transition requests
    (r"transition|handoff|arrival|drop.?feel|feel.?earned", "transition_engine", "transition", "analyze_transition", ["plan_transition"]),
    (r"smooth|seamless|boundary|crossfade", "transition_engine", "transition", "analyze_transition", ["plan_transition"]),

    # Reference requests
    (r"reference|sound.?like|style.?of|burial|daft.?punk|inspired.?by", "reference_engine", "reference", "build_reference_profile", ["analyze_reference_gaps", "plan_reference_moves"]),
    (r"compare|match|closer.?to", "reference_engine", "reference", "build_reference_profile", ["analyze_reference_gaps"]),

    # Translation requests
    (r"translat|mono|phone.?speaker|small.?speaker|earbud|headphone", "translation_engine", "translation", "check_translation", ["get_translation_issues"]),
    (r"harsh|bright.?hurt|sibilant|ear.?fatigue", "translation_engine", "translation", "check_translation", []),

    # Performance requests
    (r"live|perform|set|scene.?steer|safe.?mode|improv", "performance_engine", "performance", "get_performance_state", ["get_performance_safe_moves"]),
    (r"scene.?transition|handoff.?scene|energy.?steer", "performance_engine", "performance", "plan_scene_handoff", ["get_performance_safe_moves"]),

    # Research requests
    (r"research|how.?to|technique|tutorial|learn", "research", "research", "research_technique", []),
    (r"style.?tactic|production.?style|genre.?approach", "research", "research", "get_style_tactics", []),

    # Sample requests
    (r"sample|splice|loop|chop|flip|break(?:beat)?|one.?shot", "sample_engine", "sample", "search_samples", ["analyze_sample", "plan_sample_workflow"]),
    (r"slice|transient.?hit|slice.?mode", "sample_engine", "sample", "plan_slice_workflow", ["search_samples"]),
    (r"vocal.?sample|foley|field.?record|found.?sound", "sample_engine", "sample", "search_samples", ["analyze_sample"]),
    (r"texture.?sample|ambient.?sample|atmo.?sample", "sample_engine", "sample", "search_samples", ["suggest_sample_technique"]),
]


def _find_matching_semantic_moves(request_lower: str) -> list[dict]:
    """Search the semantic move registry for moves matching the request."""
    try:
        from ..semantic_moves.registry import _REGISTRY
    except ImportError:
        return []

    matches = []
    request_words = set(request_lower.split())

    for move in _REGISTRY.values():
        score = 0.0
        move_words = set(move.move_id.replace("_", " ").split())
        intent_words = set(move.intent.lower().split())

        # Word overlap
        overlap = request_words & (move_words | intent_words)
        score += len(overlap) * 0.3

        # Dimension keyword matching
        for dim in move.targets:
            if dim in request_lower:
                score += 0.2

        # Direct ID match
        if move.move_id.replace("_", " ") in request_lower:
            score += 1.0

        if score > 0.1:
            d = move.to_dict()
            d["match_score"] = round(score, 3)
            matches.append(d)

    matches.sort(key=lambda x: -x["match_score"])
    return matches[:3]


def _infer_workflow_mode(request_lower: str) -> str:
    """Infer the appropriate workflow mode from request language."""
    # Performance-safe keywords
    if re.search(r"live|perform|safe|set\b|show\b|gig", request_lower):
        return "performance_safe"

    # Creative search keywords
    if re.search(r"try|experiment|explore|surprise|option|variant|idea|branch", request_lower):
        return "creative_search"

    # Quick fix keywords
    if re.search(r"fix|quick|just|only|undo|revert|simple", request_lower):
        return "quick_fix"

    # Slice workflow
    if re.search(r"slice|chop|transient.?hit", request_lower):
        return "slice_workflow"

    # Sample workflows
    if re.search(r"sample|splice|foley|found.?sound|one.?shot|break(?:beat)?|flip|loop", request_lower):
        if re.search(r"arrange|section|verse|chorus|drop|bridge|hook", request_lower):
            return "sample_plus_arrangement"
        return "sample_discovery"

    # Agentic loop keywords (full autonomous)
    if re.search(r"autonomous|auto|full|everything|deep|polish|finish", request_lower):
        return "agentic_loop"

    # Default
    return "guided_workflow"


def classify_request(request: str) -> ConductorPlan:
    """Analyze a production request and route to the right engines.

    Returns a ConductorPlan with ranked engine routes and capability requirements.
    """
    lower = request.lower().strip()
    if not lower:
        return ConductorPlan(request=request, request_type="unknown",
                             notes=["Empty request — ask the user what they want to do"])

    # Score each engine by how many patterns match
    engine_scores: dict[str, dict] = {}

    for pattern, engine, req_type, entry_tool, follow_ups in _ROUTING_PATTERNS:
        if re.search(pattern, lower):
            if engine not in engine_scores:
                engine_scores[engine] = {
                    "score": 0, "request_type": req_type,
                    "entry_tool": entry_tool, "follow_ups": follow_ups,
                }
            engine_scores[engine]["score"] += 1

    if not engine_scores:
        # No engine matched — but semantic moves might still apply
        semantic_moves = _find_matching_semantic_moves(lower)
        workflow_mode = _infer_workflow_mode(lower)
        notes = ["General request — Agent OS core loop with goal vector"]
        if semantic_moves:
            notes.append(
                f"Semantic moves available: {', '.join(m['move_id'] for m in semantic_moves[:3])}. "
                "Use apply_semantic_move for intent-level execution."
            )
        return ConductorPlan(
            request=request,
            request_type="general",
            routes=[EngineRoute(
                engine="agent_os",
                priority=1,
                reason="No specific engine matched — using core Agent OS loop",
                entry_tool="get_session_kernel",
                follow_up_tools=["propose_next_best_move", "evaluate_move"],
            )],
            capability_requirements=["session_access"],
            notes=notes,
            semantic_moves=semantic_moves,
            workflow_mode=workflow_mode,
            experiment_recommended=(workflow_mode == "creative_search"),
        )

    # Sort engines by score (most matches = primary)
    sorted_engines = sorted(engine_scores.items(), key=lambda x: -x[1]["score"])

    routes: list[EngineRoute] = []
    for i, (engine, info) in enumerate(sorted_engines):
        routes.append(EngineRoute(
            engine=engine,
            priority=i + 1,
            reason=f"Matched {info['score']} keyword pattern(s)",
            entry_tool=info["entry_tool"],
            follow_up_tools=info["follow_ups"],
        ))

    primary_type = sorted_engines[0][1]["request_type"]

    # Determine capability requirements
    caps = ["session_access"]
    if any(r.engine == "mix_engine" for r in routes):
        caps.append("analyzer")
    if any(r.engine in ("reference_engine",) for r in routes):
        caps.append("offline_perception")
    if any(r.engine == "performance_engine" for r in routes):
        caps.append("live_performance_safe")

    # Notes and guidance
    notes = []
    if len(routes) > 1:
        notes.append("Multi-engine task — start with get_session_kernel for shared state")
    if any(r.engine == "mix_engine" for r in routes):
        notes.append("Mix engine works best with analyzer data — check get_capability_state")

    # V2: Search semantic moves for matching intents
    semantic_moves = _find_matching_semantic_moves(lower)

    # V2: Infer workflow mode from request language
    workflow_mode = _infer_workflow_mode(lower)

    # V2: Recommend experiments for exploratory/creative requests
    experiment_recommended = workflow_mode == "creative_search"

    if semantic_moves:
        notes.append(
            f"Semantic moves available: {', '.join(m['move_id'] for m in semantic_moves[:3])}. "
            "Use apply_semantic_move for intent-level execution."
        )

    return ConductorPlan(
        request=request,
        request_type=primary_type,
        routes=routes,
        capability_requirements=caps,
        notes=notes,
        semantic_moves=semantic_moves,
        workflow_mode=workflow_mode,
        experiment_recommended=experiment_recommended,
    )


def create_conductor_plan(
    request: str,
    mode: str = "improve",
    aggression: float = 0.5,
) -> ConductorPlan:
    """Create a full ConductorPlan with routing + budget.

    Combines classify_request (routing) with create_budget (resource limits)
    into a single plan the agent can consume.
    """
    from . import _conductor_budgets as budgets

    plan = classify_request(request)
    budget = budgets.create_budget(mode=mode, aggression=aggression)
    plan.budget = budget.to_dict()
    return plan


# ── PR4 — creative_search routing fork ──────────────────────────────────
#
# Runs only when the user intent is exploratory (workflow_mode =
# "creative_search"). Adds producer selection on top of the base
# engine routing so Wonder / synthesis_brain / composer / technique memory
# can all be consulted for branch seeds. The base classify_request is
# untouched so every existing caller and test continues to see identical
# behavior — this path is a parallel, additive classifier.


@dataclass
class CreativeSearchPlan:
    """Extended routing plan used for creative_search mode.

    Wraps a ConductorPlan with producer-selection metadata that branch
    assemblers (Wonder / synthesis_brain / composer) act on to generate
    diverse branch seeds.

    Fields:
      base_plan: the engine routing from classify_request().
      branch_sources: ordered list of producers to consult. Always contains
        "semantic_move" and "freeform"; adds "synthesis", "composer", and
        "technique" based on request content and kernel state.
      seed_hints: per-source hints passed to the producer. Shape:
        {"synthesis": {...kernel.synth_hints...}, "composer": {...}, ...}
      target_branch_count: how many branches to aim for (3 by default;
        matches the safe / strong / unexpected triptych in Preview Studio).
      freshness: 0.0-1.0, threaded from kernel.freshness.
      creativity_profile: from kernel.creativity_profile ("" when absent).
    """

    base_plan: ConductorPlan
    branch_sources: list[str] = field(default_factory=list)
    seed_hints: dict = field(default_factory=dict)
    target_branch_count: int = 3
    freshness: float = 0.5
    creativity_profile: str = ""

    def to_dict(self) -> dict:
        d = self.base_plan.to_dict()
        d["creative_search"] = {
            "branch_sources": list(self.branch_sources),
            "seed_hints": dict(self.seed_hints),
            "target_branch_count": self.target_branch_count,
            "freshness": self.freshness,
            "creativity_profile": self.creativity_profile,
        }
        # Creative-search plans always recommend experiments
        d["experiment_recommended"] = True
        return d


# Keyword families that imply a particular producer is worth consulting
# even when the kernel carries no explicit hint for it.
_SYNTH_REQUEST = re.compile(
    r"synth|patch|timbre|timbral|oscillat|wavetable|operator|filter|"
    r"modulation|lfo|envelope|drift|meld|analog|detune|spread|"
    r"haunted|lush|aggressive|warm.?pad|fat.?bass|bright.?lead",
    re.IGNORECASE,
)
_TECHNIQUE_HINT = re.compile(
    r"like.?last.?time|same.?as|recall|remember|how.?i.?did",
    re.IGNORECASE,
)


def classify_request_creative(
    request: str,
    kernel: Optional[dict] = None,
) -> CreativeSearchPlan:
    """Classify a request for creative_search mode.

    Builds on classify_request() for engine routing and adds producer
    selection so downstream branch assemblers know which sources to
    consult. This is intentionally additive — callers that don't know
    about creative_search mode can keep using classify_request() and see
    no difference.

    Producer selection:
      - "semantic_move" is always included (baseline).
      - "synthesis" added when kernel.synth_hints is non-empty OR the
        request mentions synth / patch / timbre / oscillator / filter /
        modulation / etc.
      - "composer" added when base_plan primary engine is "composition".
      - "technique" added when the kernel has enough taste evidence
        (>= 3 recorded move outcomes) OR the request suggests recalling
        a prior technique.
      - "freeform" is always the last option — a catch-all for producers
        that want to emit a seed without matching any structured category.

    When kernel is None, the function still works — it just skips the
    kernel-driven producer additions (synthesis / technique) unless the
    request text triggers them directly.
    """
    base = classify_request(request)
    kernel = kernel or {}
    request_lower = request.lower()

    sources: list[str] = ["semantic_move"]
    hints: dict = {}

    # ── Synthesis producer ──────────────────────────────────────────────
    synth_hints = kernel.get("synth_hints") or {}
    synth_matched_by_request = bool(_SYNTH_REQUEST.search(request_lower))
    if synth_hints or synth_matched_by_request:
        sources.append("synthesis")
        hints["synthesis"] = dict(synth_hints) if synth_hints else {}
        if synth_matched_by_request and not synth_hints:
            hints["synthesis"]["inferred_from_request"] = True

    # ── Composer producer (only for composition-primary routes) ────────
    if base.routes and base.routes[0].engine == "composition":
        sources.append("composer")
        hints["composer"] = {"request": request}

    # ── Technique memory producer ──────────────────────────────────────
    taste = kernel.get("taste_graph") or {}
    move_fam = taste.get("move_family_scores") or {}
    evidence = int(taste.get("evidence_count", 0) or 0)
    technique_hinted = bool(_TECHNIQUE_HINT.search(request_lower))
    if technique_hinted or (move_fam and evidence >= 3):
        sources.append("technique")
        preferred = []
        for fam, s in move_fam.items():
            if isinstance(s, dict) and s.get("score", 0) > 0.2:
                preferred.append(fam)
        hints["technique"] = {
            "preferred_families": preferred[:3],
            "hinted_by_request": technique_hinted,
        }

    # ── Freeform always available ──────────────────────────────────────
    sources.append("freeform")

    return CreativeSearchPlan(
        base_plan=base,
        branch_sources=sources,
        seed_hints=hints,
        target_branch_count=3,
        freshness=float(kernel.get("freshness", 0.5) or 0.5),
        creativity_profile=kernel.get("creativity_profile", "") or "",
    )

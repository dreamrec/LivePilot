"""Research Engine — targeted and deep research synthesis for production techniques.

Searches the device atlas, technique memory, and optionally web sources to answer
production questions. Synthesizes findings into structured TechniqueCards.

Zero external dependencies beyond stdlib. The MCP tool wrappers in research.py
handle data fetching; this module handles synthesis and ranking.

Design: spec at docs/specs/2026-04-08-phase2-4-roadmap.md, Round 3 (3.1, 3.2).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from ._agent_os_engine import TechniqueCard


# ── Research Results ─────────────────────────────────────────────────

@dataclass
class ResearchFinding:
    """A single finding from a research source."""
    source_type: str  # "device_atlas", "memory", "web", "corpus"
    source_id: str  # e.g., "Wavetable", "mem_042", "url:..."
    relevance: float  # 0-1, how relevant to the query
    content: str  # the actual finding text
    metadata: dict = field(default_factory=dict)  # source-specific extras

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ResearchResult:
    """Aggregated research output."""
    query: str
    scope: str  # "targeted" or "deep"
    findings: list[ResearchFinding] = field(default_factory=list)
    technique_card: Optional[TechniqueCard] = None
    confidence: float = 0.0  # 0-1, overall confidence in findings
    sources_searched: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        # TechniqueCard.to_dict() for cleaner output
        if self.technique_card:
            d["technique_card"] = self.technique_card.to_dict()
        d["finding_count"] = len(self.findings)
        return d


# ── Query Analysis ───────────────────────────────────────────────────

# Common production technique keywords → likely device families
_TECHNIQUE_KEYWORDS: dict[str, list[str]] = {
    "sidechain": ["Compressor", "Glue Compressor", "Auto Filter"],
    "reverb": ["Reverb", "Convolution Reverb", "Hybrid Reverb"],
    "delay": ["Delay", "Echo", "Filter Delay", "Grain Delay"],
    "distortion": ["Saturator", "Overdrive", "Pedal", "Amp"],
    "eq": ["EQ Eight", "EQ Three", "Channel EQ"],
    "compress": ["Compressor", "Glue Compressor", "Multiband Dynamics"],
    "filter": ["Auto Filter", "EQ Eight"],
    "modulation": ["LFO", "Chorus-Ensemble", "Phaser-Flanger"],
    "granular": ["Granulator II", "Grain Delay"],
    "sampling": ["Simpler", "Sampler", "Drum Rack"],
    "synthesis": ["Wavetable", "Operator", "Analog", "Drift"],
    "bass": ["Operator", "Analog", "Wavetable", "Saturator"],
    "pad": ["Wavetable", "Drift", "Reverb", "Chorus-Ensemble"],
    "drums": ["Drum Rack", "Simpler", "Compressor", "Saturator"],
    "vocals": ["Compressor", "EQ Eight", "Reverb", "Delay"],
    "mastering": ["Multiband Dynamics", "Limiter", "EQ Eight", "Utility"],
    "width": ["Utility", "Chorus-Ensemble", "Haas", "Mid/Side"],
    "warmth": ["Saturator", "Amp", "Analog"],
    "space": ["Reverb", "Convolution Reverb", "Delay"],
    "glue": ["Glue Compressor", "Saturator", "Bus compression"],
}


def analyze_query(query: str) -> dict:
    """Analyze a research query to extract intent, keywords, and likely devices.

    Returns: {keywords, likely_devices, technique_category, specificity}
    """
    lower = query.lower().strip()
    words = re.findall(r'\b[a-z]+\b', lower)

    # Match technique keywords
    matched_devices: list[str] = []
    matched_categories: list[str] = []

    for keyword, devices in _TECHNIQUE_KEYWORDS.items():
        if keyword in lower:
            matched_devices.extend(devices)
            matched_categories.append(keyword)

    # Deduplicate
    matched_devices = list(dict.fromkeys(matched_devices))

    # Specificity: how detailed is the query?
    specificity = min(1.0, len(words) / 10.0)
    if matched_categories:
        specificity = min(1.0, specificity + 0.2)

    return {
        "keywords": words,
        "likely_devices": matched_devices[:5],
        "technique_categories": matched_categories,
        "specificity": round(specificity, 2),
    }


# ── Finding Ranking ──────────────────────────────────────────────────

def _score_finding_relevance(finding_text: str, query_words: list[str]) -> float:
    """Score how relevant a finding is to the query keywords."""
    if not query_words or not finding_text:
        return 0.0

    lower_text = finding_text.lower()
    matches = sum(1 for w in query_words if w in lower_text)
    return min(1.0, matches / max(len(query_words), 1))


def rank_findings(findings: list[ResearchFinding]) -> list[ResearchFinding]:
    """Sort findings by relevance, deduplicating low-value entries."""
    # Sort by relevance descending
    ranked = sorted(findings, key=lambda f: -f.relevance)

    # Deduplicate: skip findings that are too similar to a higher-ranked one
    seen_content: set[str] = set()
    deduped = []
    for f in ranked:
        # Simple dedup: check if first 50 chars already seen
        sig = f.content[:50].lower().strip()
        if sig not in seen_content:
            deduped.append(f)
            seen_content.add(sig)

    return deduped[:10]  # Cap at 10 findings


# ── Targeted Research ────────────────────────────────────────────────

def targeted_research(
    query: str,
    device_atlas_results: list[dict],
    memory_results: list[dict],
    corpus_results: Optional[list[dict]] = None,
) -> ResearchResult:
    """Synthesize targeted research from device atlas + memory.

    device_atlas_results: list of device reference entries (from get_device_reference)
    memory_results: list of technique memories (from memory_list)
    corpus_results: optional additional reference entries

    Returns: ResearchResult with ranked findings and synthesized technique card.
    """
    query_info = analyze_query(query)
    findings: list[ResearchFinding] = []
    sources_searched = []

    # 1. Device atlas findings.
    # BUG-B43 fix: device_atlas_results is a list of search_browser
    # RESPONSES (each with {path, items: [...], count, ...}) — NOT a
    # list of device entries. The old code read response.get("name")
    # which always returned "" because the response has no top-level
    # name. Every finding came back as "Device: Unknown". We now
    # flatten the responses, look up each item's real atlas metadata,
    # and build one finding per resolved device.
    if device_atlas_results:
        sources_searched.append("device_atlas")
        flattened_entries: list[dict] = []
        for response in device_atlas_results:
            if not isinstance(response, dict):
                continue
            # Accept old shape (single device dict) for forward compat
            if response.get("name") and not response.get("items"):
                flattened_entries.append(response)
                continue
            items = response.get("items") or response.get("results") or []
            for item in items:
                if not isinstance(item, dict):
                    continue
                flattened_entries.append({
                    "name": item.get("name", ""),
                    "uri": item.get("uri", ""),
                    "category": response.get("path", ""),
                    "is_loadable": item.get("is_loadable", False),
                })

        for entry in flattened_entries:
            name = entry.get("name", "")
            if not name:
                continue  # skip phantom empties
            # Try to enrich with atlas lookup — gives real description,
            # character_tags, genres.
            try:
                from ..atlas import _atlas_instance as _atlas
                if _atlas is not None:
                    full = _atlas.lookup(name)
                    if full:
                        entry = {**full, **entry}
            except Exception:
                pass

            text = _format_device_finding(entry)
            relevance = _score_finding_relevance(text, query_info["keywords"])
            if name in query_info["likely_devices"]:
                relevance = min(1.0, relevance + 0.3)

            findings.append(ResearchFinding(
                source_type="device_atlas",
                source_id=name,
                relevance=round(relevance, 3),
                content=text,
                metadata={
                    "device_name": name,
                    "category": entry.get("category", ""),
                },
            ))

    # 2. Memory findings (technique cards, outcomes, research notes)
    if memory_results:
        sources_searched.append("memory")
        for mem in memory_results:
            payload = mem.get("payload", {})
            if isinstance(payload, dict):
                text = _format_memory_finding(mem)
                relevance = _score_finding_relevance(text, query_info["keywords"])

                # Boost technique cards (more structured = more useful)
                mem_type = mem.get("type", "")
                if mem_type == "technique_card":
                    relevance = min(1.0, relevance + 0.2)

                findings.append(ResearchFinding(
                    source_type="memory",
                    source_id=mem.get("id", "unknown"),
                    relevance=round(relevance, 3),
                    content=text,
                    metadata={"memory_type": mem_type},
                ))

    # 3. Corpus findings (additional references)
    if corpus_results:
        sources_searched.append("corpus")
        for entry in corpus_results:
            text = entry.get("content", entry.get("text", str(entry)))
            relevance = _score_finding_relevance(text, query_info["keywords"])
            findings.append(ResearchFinding(
                source_type="corpus",
                source_id=entry.get("id", "corpus"),
                relevance=round(relevance, 3),
                content=text[:500],  # Cap length
            ))

    # Rank and deduplicate
    ranked = rank_findings(findings)

    # Synthesize technique card from top findings
    card = _synthesize_technique_card(query, ranked, query_info)

    # Overall confidence
    if not ranked:
        confidence = 0.0
    else:
        top_relevances = [f.relevance for f in ranked[:3]]
        confidence = sum(top_relevances) / len(top_relevances)

    return ResearchResult(
        query=query,
        scope="targeted",
        findings=ranked,
        technique_card=card,
        confidence=round(confidence, 3),
        sources_searched=sources_searched,
    )


def _format_device_finding(entry: dict) -> str:
    """Format a device atlas entry into a readable finding."""
    name = entry.get("name", "Unknown")
    category = entry.get("category", "")
    description = entry.get("description", "")
    params = entry.get("key_parameters", entry.get("parameters", []))

    parts = [f"Device: {name}"]
    if category:
        parts.append(f"Category: {category}")
    if description:
        parts.append(description[:200])
    if params and isinstance(params, list):
        param_names = [p.get("name", p) if isinstance(p, dict) else str(p) for p in params[:5]]
        parts.append(f"Key params: {', '.join(param_names)}")

    return " | ".join(parts)


def _format_memory_finding(mem: dict) -> str:
    """Format a memory entry into a readable finding."""
    mem_type = mem.get("type", "unknown")
    payload = mem.get("payload", {})

    if mem_type == "technique_card":
        problem = payload.get("problem", "")
        method = payload.get("method", "")
        devices = payload.get("devices", [])
        return f"Technique: {problem} | Method: {method} | Devices: {', '.join(devices)}"
    elif mem_type == "outcome":
        move = payload.get("move", {})
        score = payload.get("score", 0)
        move_name = move.get("name", "unknown") if isinstance(move, dict) else str(move)
        return f"Outcome: {move_name} (score: {score:.2f})"
    else:
        # Research or note
        content = payload.get("content", payload.get("text", str(payload)))
        if isinstance(content, str):
            return content[:300]
        return str(content)[:300]


def _synthesize_technique_card(
    query: str,
    findings: list[ResearchFinding],
    query_info: dict,
) -> Optional[TechniqueCard]:
    """Synthesize a technique card from research findings."""
    if not findings:
        return None

    # Collect devices from findings
    devices: list[str] = []
    for f in findings:
        if f.source_type == "device_atlas":
            dev = f.metadata.get("device_name", "")
            if dev and dev not in devices:
                devices.append(dev)
        elif f.source_type == "memory" and f.metadata.get("memory_type") == "technique_card":
            # Pull devices from technique card memories
            pass  # Already in the finding content

    # Also include query-predicted devices
    for d in query_info.get("likely_devices", []):
        if d not in devices:
            devices.append(d)

    # Build method from top findings
    method_parts = []
    for f in findings[:3]:
        if f.relevance >= 0.3:
            method_parts.append(f.content[:150])

    method = " → ".join(method_parts) if method_parts else f"Research findings for: {query}"

    # Build verification from technique categories
    verification = []
    for cat in query_info.get("technique_categories", []):
        verification.append(f"Check {cat} results with analyzer")

    if not verification:
        verification = ["Listen for intended effect", "Compare before/after with analyzer"]

    return TechniqueCard(
        problem=query,
        context=query_info.get("technique_categories", []),
        devices=devices[:5],
        method=method,
        verification=verification,
        evidence={"scope": "targeted", "finding_count": len(findings)},
    )


# ── Deep Research ────────────────────────────────────────────────────

def deep_research(
    query: str,
    web_results: list[dict],
    device_atlas_results: list[dict],
    memory_results: list[dict],
    corpus_results: Optional[list[dict]] = None,
) -> ResearchResult:
    """Multi-source synthesis: targeted sources + web search results.

    web_results: list of {url, title, snippet} from web search
    Other params same as targeted_research.

    Returns: ResearchResult with deeper analysis and multiple technique cards.
    """
    # Start with targeted research
    targeted = targeted_research(query, device_atlas_results, memory_results, corpus_results)

    query_info = analyze_query(query)
    sources_searched = list(targeted.sources_searched)

    # Add web findings
    web_findings: list[ResearchFinding] = []
    if web_results:
        sources_searched.append("web")
        for wr in web_results:
            title = wr.get("title", "")
            snippet = wr.get("snippet", wr.get("text", ""))
            url = wr.get("url", "")

            text = f"{title}: {snippet}"
            relevance = _score_finding_relevance(text, query_info["keywords"])

            # Boost results from known production sources
            if any(domain in url.lower() for domain in
                   ["ableton.com", "soundonsound.com", "musicradar.com",
                    "attackmagazine.com", "producerhive.com"]):
                relevance = min(1.0, relevance + 0.15)

            web_findings.append(ResearchFinding(
                source_type="web",
                source_id=url or title,
                relevance=round(relevance, 3),
                content=text[:500],
                metadata={"url": url, "title": title},
            ))

    # Merge and re-rank all findings
    all_findings = targeted.findings + web_findings
    ranked = rank_findings(all_findings)

    # Synthesize card from richer data
    card = _synthesize_technique_card(query, ranked, query_info)

    # Higher confidence with more sources
    if not ranked:
        confidence = 0.0
    else:
        top_relevances = [f.relevance for f in ranked[:3]]
        base_confidence = sum(top_relevances) / len(top_relevances)
        source_bonus = min(0.15, len(sources_searched) * 0.05)
        confidence = min(1.0, base_confidence + source_bonus)

    return ResearchResult(
        query=query,
        scope="deep",
        findings=ranked,
        technique_card=card,
        confidence=round(confidence, 3),
        sources_searched=sources_searched,
    )


# ── Style Tactics (Round 4) ──────────────────────────────────────────

@dataclass
class StyleTactic:
    """Artist/genre reference study as a reusable composition tactic."""
    artist_or_genre: str
    tactic_name: str
    arrangement_patterns: list[str] = field(default_factory=list)
    device_chain: list[dict] = field(default_factory=list)
    automation_gestures: list[str] = field(default_factory=list)
    verification: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# Built-in style tactic library — common production approaches by genre/artist
STYLE_TACTIC_LIBRARY: list[StyleTactic] = [
    StyleTactic(
        artist_or_genre="burial",
        tactic_name="ghostly_reverb_treatment",
        arrangement_patterns=["sparse_intro", "gradual_buildup", "sudden_strip_back"],
        device_chain=[
            {"name": "Reverb", "params": {"Decay Time": 4.5, "Dry/Wet": 0.6}},
            {"name": "Auto Filter", "params": {"Frequency": 800, "Resonance": 0.4}},
            {"name": "Utility", "params": {"Width": 0.7}},
        ],
        automation_gestures=["conceal", "drift", "punctuate"],
        verification=["Check reverb tail doesn't mud the low end", "Verify width feels intimate"],
    ),
    StyleTactic(
        artist_or_genre="daft punk",
        tactic_name="filter_disco_sweep",
        arrangement_patterns=["4_bar_filter_open", "loop_with_variation", "energy_plateau"],
        device_chain=[
            {"name": "Auto Filter", "params": {"Frequency": 200, "Resonance": 0.6}},
            {"name": "Saturator", "params": {"Drive": 8, "Dry/Wet": 0.4}},
            {"name": "Compressor", "params": {"Ratio": 4, "Attack": 10}},
        ],
        automation_gestures=["reveal", "lift", "release"],
        verification=["Filter sweep should feel musical, not mechanical", "Check groove isn't crushed"],
    ),
    StyleTactic(
        artist_or_genre="techno",
        tactic_name="rolling_hypnotic_groove",
        arrangement_patterns=["long_intro_16bars", "minimal_variation", "subtle_addition_per_8bars"],
        device_chain=[
            {"name": "Compressor", "params": {"Attack": 0.1, "Release": 100, "Ratio": 6}},
            {"name": "Delay", "params": {"Dry/Wet": 0.15, "Feedback": 0.3}},
            {"name": "EQ Eight", "params": {}},
        ],
        automation_gestures=["drift", "inhale", "release"],
        verification=["Groove should be hypnotic not boring", "Check low-end stays clean"],
    ),
    StyleTactic(
        artist_or_genre="ambient",
        tactic_name="evolving_texture_bed",
        arrangement_patterns=["very_slow_reveal", "32bar_sections", "layered_textures"],
        device_chain=[
            {"name": "Reverb", "params": {"Decay Time": 8.0, "Dry/Wet": 0.8}},
            {"name": "Chorus-Ensemble", "params": {"Rate 1": 0.3}},
            {"name": "Delay", "params": {"Dry/Wet": 0.3, "Feedback": 0.5}},
        ],
        automation_gestures=["drift", "reveal", "sink"],
        verification=["Texture should feel alive, not static", "Check nothing competes for attention"],
    ),
    StyleTactic(
        artist_or_genre="trap",
        tactic_name="808_bounce_pattern",
        arrangement_patterns=["8bar_loop_base", "hihat_triplet_fills", "vocal_chop_hooks"],
        device_chain=[
            {"name": "Operator", "params": {}},
            {"name": "Saturator", "params": {"Drive": 12}},
            {"name": "Glue Compressor", "params": {"Ratio": 4, "Attack": 0.1}},
        ],
        automation_gestures=["punctuate", "release", "lift"],
        verification=["808 should hit hard but not clip", "Hi-hats should groove not machine-gun"],
    ),
    StyleTactic(
        artist_or_genre="lo-fi",
        tactic_name="dusty_warmth",
        arrangement_patterns=["simple_loop_structure", "minimal_sections", "fade_endings"],
        device_chain=[
            {"name": "Saturator", "params": {"Drive": 5, "Dry/Wet": 0.5}},
            {"name": "EQ Eight", "params": {}},
            {"name": "Auto Filter", "params": {"Frequency": 3000}},
        ],
        automation_gestures=["conceal", "drift", "sink"],
        verification=["Should feel warm not muddy", "High-end roll-off should sound natural"],
    ),
]


def get_style_tactics(
    artist_or_genre: str,
    memory_tactics: Optional[list[dict]] = None,
) -> list[StyleTactic]:
    """Find style tactics matching an artist or genre query.

    Searches the built-in library and optionally user-saved tactics from memory.
    """
    query = artist_or_genre.lower().strip()
    results: list[StyleTactic] = []

    # Search built-in library
    for tactic in STYLE_TACTIC_LIBRARY:
        if query in tactic.artist_or_genre.lower() or query in tactic.tactic_name.lower():
            results.append(tactic)

    # Also partial match on arrangement patterns
    if not results:
        for tactic in STYLE_TACTIC_LIBRARY:
            if any(query in p.lower() for p in tactic.arrangement_patterns):
                results.append(tactic)

    # Search user memory tactics.
    # BUG-B18 fix: TechniqueStore.search() strips the payload from
    # summaries, so `mem.get("payload", {})` was always empty and the
    # old match-by-payload.artist_or_genre code never fired. Users who
    # saved 3 "Prefuse73" techniques via memory_learn got back 0
    # tactics from get_style_tactics("prefuse73"). We now match on
    # name + tags + qualities.summary + payload (if present) and
    # adapt the memory-entry to a StyleTactic regardless of whether
    # the caller formatted the payload in the exact style_tactic shape.
    if memory_tactics:
        for mem in memory_tactics:
            if not isinstance(mem, dict):
                continue
            # Build the searchable text from whichever shape the memory
            # entry uses. This is lenient on purpose — saved techniques
            # don't need to pre-commit to a schema to surface here.
            name = str(mem.get("name", ""))
            tags = mem.get("tags", []) or []
            qualities = mem.get("qualities", {}) or {}
            summary = str(qualities.get("summary", "") or "")
            payload = mem.get("payload", {}) or {}

            searchable = " ".join([
                name.lower(), summary.lower(),
                " ".join(str(t).lower() for t in tags),
                str(payload.get("artist_or_genre", "")).lower(),
                str(payload.get("tactic_name", "")).lower(),
            ])
            if query not in searchable:
                continue

            # Adapt to StyleTactic — prefer payload fields when present,
            # fall back to the summary for arrangement_patterns, etc.
            artist_or_genre = str(
                payload.get("artist_or_genre")
                or next((t for t in tags if query in str(t).lower()), "")
                or query
            )
            tactic_name = str(payload.get("tactic_name") or name or summary[:40])
            arrangement_patterns = (
                payload.get("arrangement_patterns")
                or [summary] if summary else []
            )
            device_chain = payload.get("device_chain", []) or []
            automation_gestures = payload.get("automation_gestures", []) or []
            verification = payload.get("verification", []) or []

            results.append(StyleTactic(
                artist_or_genre=artist_or_genre,
                tactic_name=tactic_name,
                arrangement_patterns=arrangement_patterns,
                device_chain=device_chain,
                automation_gestures=automation_gestures,
                verification=verification,
            ))

    return results

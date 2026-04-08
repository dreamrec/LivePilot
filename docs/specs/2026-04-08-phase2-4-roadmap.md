# LivePilot Phase 2-4 Roadmap — Agent OS + Composition Engine

**Date:** 2026-04-08
**Status:** Active
**Scope:** All remaining phases from AGENT_OS_V1.md (Phase 2-3) and COMPOSITION_ENGINE_V1.md (Phase 2-4)
**Ordering:** Musical impact priority — each round makes the agent meaningfully smarter

---

## Current State (Rounds 1-4 Complete)

- **236 tools** across 32 domains
- **Agent OS V1**: GoalVector (17 quality dims), WorldModel, SonicCritic (6 heuristics), TechnicalCritic, evaluation scorer with hard-rule keep/undo
- **Composition Engine V1**: SectionGraph, PhraseGrid, RoleGraph (section-aware), FormCritic, SectionIdentityCritic, PhraseCritic, GesturePlanner (9 intents)
- **Round 1 (complete)**: HarmonyField, TransitionCritic, OutcomeAnalyzer, structural critic wiring
- **Round 2 (complete)**: MotifGraph, GestureTemplates (11), TechniqueCards, SectionOutcomes
- **Round 3 (complete)**: ResearchEngine (targeted+deep), PlannerEngine (5 styles), EmotionalArcCritic (5 checks), technique mining
- **Round 4 (complete)**: TasteModel (real taste_fit), StyleTactics (6 built-in), CrossSectionCritic, FormEngine (9 transforms), OrchestrationPlanner, CompositionTaste, orchestral_reassignment
- **484+ tests** passing

---

## Round 1: "The Ears Get Smarter" — Musical Intelligence

### 1.1 Harmony Field (Composition P2)

**What:** Integrate existing theory+harmony tools into the composition world model. Each section gets a `HarmonyField` with key, mode, chord progression, voice-leading quality, harmonic instability, and resolution potential.

**Engine additions to `_composition_engine.py`:**
```python
@dataclass
class HarmonyField:
    key: str                     # "C", "F#"
    mode: str                    # "minor", "dorian", etc.
    confidence: float            # key detection confidence
    chord_progression: list[str] # ["Cm", "Ab", "Fm", "Gm"]
    voice_leading_quality: float # 0-1 from analyze_voice_leading
    instability: float           # 0-1, how far from tonal center
    resolution_potential: float  # 0-1, tendency toward resolution
```

**Data sources:** `identify_scale`, `analyze_harmony`, `classify_progression`, `find_voice_leading_path` (all existing tools, no new Ableton commands)

**New MCP tool:** `get_harmony_field(section_index)` — returns harmony analysis for a section

**Integration:** `analyze_composition` includes HarmonyField per section in output. HarmonyField feeds into transition critic and section identity critic.

### 1.2 Transition Critic (Composition P2)

**What:** Analyze boundaries between adjacent sections. Detect: hard cuts (no transition), weak builds (energy but no musical tension), missing pre-arrival subtraction, transitions that break groove.

**Engine additions to `_composition_engine.py`:**
```python
def run_transition_critic(sections, roles, harmony_fields) -> list[CompositionIssue]:
    # For each pair of adjacent sections:
    # 1. Energy delta — is there a meaningful shift?
    # 2. Density change — do elements enter/exit?
    # 3. Harmonic movement — does the key/chord change support the transition?
    # 4. Role rotation — do foreground voices change?
    # 5. Pre-arrival subtraction — does the section before a peak thin out?
```

**Issue types:**
- `hard_cut_transition` — no energy/density change at boundary
- `weak_build` — energy rises but no harmonic support
- `no_pre_arrival_subtraction` — peak section not preceded by thinning
- `groove_break_at_transition` — rhythmic role drops out at boundary
- `harmonic_non_sequitur` — key change without voice-leading path

### 1.3 Outcome Memory Analysis (Agent OS P2)

**What:** Analyze accumulated `outcome` memories to identify patterns — what types of moves does this user keep vs undo? Which quality dimensions tend to improve? What devices/parameters are most effective?

**Engine additions to `_agent_os_engine.py`:**
```python
def analyze_outcome_history(outcomes: list[dict]) -> dict:
    # Returns:
    # - keep_rate: overall % of moves kept
    # - dimension_success: {dim: avg_improvement_when_kept}
    # - common_kept_moves: most frequent kept action types
    # - common_undone_moves: most frequent undone actions
    # - taste_vector: inferred dimension preferences from history
```

**New MCP tool:** `analyze_outcomes(limit=50)` — reads outcome memories, returns taste analysis

**Integration:** `build_world_model` includes taste hints from outcome analysis. The agent consults this before choosing moves.

### 1.4 Structural Critic Wiring (Agent OS P2)

**What:** Wire the Composition Engine's 3 critics (form, section identity, phrase) into the Agent OS world model as the "structural critic" that Phase 1 deferred.

**Changes:** `build_world_model` in `agent_os.py` calls `analyze_composition` and includes structural issues alongside sonic/technical issues.

**No new tools** — this is wiring existing tools together.

---

## Round 2: "Pattern Recognition" — Motif & Gesture Intelligence

### 2.1 Motif Graph (Composition P2)

**What:** Detect recurring melodic/rhythmic patterns across clips. Track where motifs appear, how often, salience (how memorable), and fatigue risk (overuse).

**Engine: new `_motif_engine.py`** (isolated — pattern detection is complex enough for its own module)
```python
@dataclass
class MotifUnit:
    motif_id: str
    kind: str              # "melodic", "rhythmic", "intervallic"
    pitch_contour: list[int]  # relative intervals
    occurrences: list[dict]   # [{section_id, track_index, start_bar}]
    salience: float        # 0-1, how distinctive/memorable
    fatigue_risk: float    # 0-1, overuse danger
    suggested_developments: list[str]  # ["register_shift", "rhythmic_variation"]
```

**Algorithm:** Extract pitch contours and rhythm patterns from notes → find repeated subsequences → score by frequency and distinctiveness

**New MCP tool:** `get_motif_graph()` — returns detected motifs with occurrences and suggestions

### 2.2 Automation Gesture Templates (Composition P2)

**What:** Compound gesture sequences for common arrangement patterns. Higher-level than single gestures.

**Engine additions to `_composition_engine.py`:**
```python
GESTURE_TEMPLATES = {
    "pre_arrival_vacuum": [
        {"intent": "inhale", "offset_bars": -4},
        {"intent": "release", "offset_bars": 0},
    ],
    "sectional_width_bloom": [
        {"intent": "conceal", "offset_bars": -2},
        {"intent": "reveal", "offset_bars": 0},
        {"intent": "drift", "offset_bars": 2},
    ],
    "phrase_end_throw": [
        {"intent": "punctuate", "offset_bars": -1},
    ],
    "outro_decay_dissolve": [
        {"intent": "conceal", "offset_bars": 0, "duration_bars": 8},
        {"intent": "sink", "offset_bars": 4, "duration_bars": 8},
    ],
    # ... 8 more templates from spec section 12.6
}
```

**New MCP tool:** `apply_gesture_template(template_name, target_tracks, anchor_bar)` — returns sequence of gesture plans

### 2.3 Technique Cards (Agent OS P2)

**What:** Research outputs become structured, reusable recipe cards — not just text. Each card has: problem, context, devices, method, verification, evidence.

**Engine additions to `_agent_os_engine.py`:**
```python
@dataclass
class TechniqueCard:
    problem: str
    context: list[str]       # genre/style tags
    devices: list[str]       # what to load
    method: str              # step-by-step
    verification: list[str]  # what to check after
    evidence: dict           # sources, in_session_tested
```

**New MCP tool:** `get_technique_card(query)` — searches memory for technique cards matching query, returns structured recipes

**Storage:** Uses existing memory system with `type="technique_card"` (new valid type)

### 2.4 Section Outcome Memory (Composition P2)

**What:** Track which composition moves worked in which section types — personalized over time.

**Engine additions:**
```python
def analyze_section_outcomes(outcomes: list[dict]) -> dict:
    # Groups outcomes by section_type
    # Returns: {section_type: {move: avg_score, keep_rate}}
```

**New MCP tool:** `get_section_outcomes(section_type)` — returns success rates for moves in this section type

---

## Round 3: "Research & Form" — Knowledge & Long-Form Reasoning

### 3.1 Targeted Research Mode (Agent OS P2)

**What:** When `research_mode="targeted"`, the agent searches the device atlas, reference corpus, and memory before acting. For unknown plugins/devices, it looks up documentation.

**New engine: `_research_engine.py`:**
```python
def targeted_research(query: str, corpus: dict, memory_results: list) -> dict:
    # 1. Search device atlas references
    # 2. Search memory for related techniques
    # 3. Synthesize findings into a TechniqueCard
    # Returns: {findings, technique_card, confidence, sources}
```

**New MCP tool:** `research_technique(query, scope="targeted")` — searches corpus + memory, returns findings

### 3.2 Deep Research Mode (Agent OS P3)

**What:** Multi-source synthesis for unfamiliar territory. Web search + corpus + memory + device atlas.

**Extension to `_research_engine.py`:**
```python
def deep_research(query: str, web_results: list, corpus: dict, memory: list) -> dict:
    # 1. All targeted research sources
    # 2. Web search results (if available)
    # 3. Cross-reference and rank
    # 4. Distill into technique cards
    # Returns: {findings, cards: list[TechniqueCard], confidence}
```

**New MCP tool:** `deep_research(query)` — requires web access (graceful degradation without)

### 3.3 Loop-to-Song Planner (Composition P3)

**What:** Transform a single loop into a full arrangement. Analyzes the loop's musical content, proposes a section structure, and plans element reveal/addition/subtraction order.

**New engine: `_planner_engine.py`:**
```python
def plan_arrangement_from_loop(
    loop_analysis: CompositionAnalysis,
    target_duration_bars: int = 128,
    style: str = "electronic",
) -> dict:
    # 1. Identify loop identity (what makes it recognizable)
    # 2. Propose section sequence (intro → verse → build → drop → bridge → outro)
    # 3. Plan element additions per section
    # 4. Plan reveal order (what enters when)
    # 5. Plan gesture automation for transitions
    # Returns: {sections, element_plan, gesture_plan, estimated_bars}
```

**New MCP tool:** `plan_arrangement(target_bars, style)` — returns full arrangement blueprint

### 3.4 Emotional Arc Critic (Composition P3)

**What:** Does the arrangement tell an emotional story? Analyzes tension curve across sections. Detects: monotone energy, all-climax (no rest), missing catharsis, build without payoff.

**Engine additions to `_composition_engine.py`:**
```python
def run_emotional_arc_critic(sections, harmony_fields) -> list[CompositionIssue]:
    # Build tension curve from: energy, harmonic instability, density
    # Check: does it have rise + fall? Peak in second half?
    # Issue types: monotone_arc, all_climax, build_no_payoff, no_resolution
```

### 3.5 Background Technique Mining (Agent OS P3)

**What:** Passively distill techniques from regular sessions. When the agent detects a novel approach that worked, it auto-creates a technique card.

**Engine additions to `_agent_os_engine.py`:**
```python
def should_mine_technique(outcome: dict) -> bool:
    # Returns True if: score > 0.7, dimension improvement > 0.15,
    # and similar technique not already in memory

def mine_technique_from_outcome(outcome: dict) -> TechniqueCard:
    # Extracts: what was done, what improved, what context
```

**No new MCP tool** — this logic runs inside `evaluate_move` when conditions are met, suggesting a `memory_learn` call.

---

## Round 4: "Personalization & Mastery" — Taste & Advanced Composition

### 4.1 User Personalization / Taste Models (Agent OS P3)

**What:** Richer scoring from accumulated taste data. The evaluation score's `taste_fit` component (currently 0.0 placeholder) becomes real.

**Engine additions to `_agent_os_engine.py`:**
```python
def compute_taste_fit(goal: GoalVector, outcome_history: list[dict]) -> float:
    # Analyze: which dimensions does this user care about most?
    # Weight the evaluation score toward their preferences
    # Returns: 0.0-1.0 taste alignment score
```

**Changes:** `compute_evaluation_score` uses real `taste_fit` instead of 0.0 placeholder.

### 4.2 Style Tactic Cards (Composition P3)

**What:** Artist/genre reference studies as reusable composition tactics. "Burial-style reverb treatment" → a card with specific device settings and arrangement patterns.

**Engine additions to `_research_engine.py`:**
```python
@dataclass
class StyleTactic:
    artist_or_genre: str
    tactic_name: str
    arrangement_patterns: list[str]
    device_chain: list[dict]
    automation_gestures: list[str]
    verification: list[str]
```

**New MCP tool:** `get_style_tactics(artist_or_genre)` — returns relevant tactics from library + research

### 4.3 Multi-Section Reasoning (Composition P3)

**What:** Reason across the entire arrangement coherently. Currently critics analyze sections in isolation; this adds cross-section awareness.

**Engine additions to `_composition_engine.py`:**
```python
def run_cross_section_critic(sections, roles, harmony_fields, motifs) -> list[CompositionIssue]:
    # Checks across ALL sections:
    # - Is there a clear reveal order? (elements shouldn't all appear at once)
    # - Do foreground voices rotate? (same lead in every section = fatigue)
    # - Is harmonic pacing appropriate? (rapid changes everywhere = chaos)
    # - Do motifs develop? (same motif unchanged = repetition fatigue)
```

### 4.4 Advanced Form Transformation (Composition P4)

**What:** Radical structural moves — reorder sections, expand a 4-bar loop into a 16-bar section, compress a verbose arrangement, insert a bridge.

**Engine: new `_form_engine.py`:**
```python
def transform_section_order(sections, transformation) -> list[SectionNode]:
    # Transformations: "insert_bridge_before_final_chorus", "swap_verse_positions",
    # "extend_intro_by_4_bars", "compress_outro"
```

**New MCP tool:** `transform_section(transformation, section_index)` — returns proposed new section graph

### 4.5 Motif Transformation Library (Composition P4)

**What:** Apply musical transformations to detected motifs — inversion, augmentation, diminution, fragmentation, register shift, orchestral reassignment.

**Engine additions to `_motif_engine.py`:**
```python
def transform_motif(motif: MotifUnit, transformation: str) -> list[dict]:
    # Transformations: "inversion", "augmentation", "diminution",
    # "fragmentation", "register_shift_up", "register_shift_down",
    # "orchestral_reassignment"
    # Returns: new note array ready for add_notes
```

**New MCP tool:** `transform_motif(motif_id, transformation)` — returns transformed notes

### 4.6 Cross-Section Orchestration Planning (Composition P4)

**What:** Plan which instruments play in which sections across the full arrangement. Prevents "everything plays everywhere" syndrome.

**Engine additions to `_planner_engine.py`:**
```python
def plan_orchestration(sections, roles, motifs) -> dict:
    # Returns: {section_id: {track_index: "active"|"silent"|"reduced"}}
    # Rules: no more than 3 foreground voices, bass+kick always paired,
    # textures rotate, hook appears in chorus but not verse
```

### 4.7 Personalized Composition Taste Models (Composition P4)

**What:** Composition advice shaped by this user's history. "You tend to prefer sparser intros" → auto-adjust section density targets.

**Engine additions:**
```python
def build_composition_taste_model(section_outcomes: list) -> dict:
    # Aggregate section outcomes → per-section-type preferences
    # Returns: {section_type: {preferred_density, preferred_foreground_count, ...}}
```

---

## File Structure

### New Files (by round)

| Round | File | Purpose |
|-------|------|---------|
| 1 | (extend existing) | HarmonyField, TransitionCritic, OutcomeAnalyzer |
| 2 | `mcp_server/tools/_motif_engine.py` | Motif detection + transformation |
| 2 | `mcp_server/tools/motif.py` | Motif MCP tools |
| 2 | `tests/test_motif_engine.py` | Motif tests |
| 3 | `mcp_server/tools/_research_engine.py` | Research synthesis |
| 3 | `mcp_server/tools/research.py` | Research MCP tools |
| 3 | `mcp_server/tools/_planner_engine.py` | Arrangement planning |
| 3 | `mcp_server/tools/planner.py` | Planner MCP tools |
| 3 | `tests/test_research_engine.py` | Research tests |
| 3 | `tests/test_planner_engine.py` | Planner tests |
| 4 | `mcp_server/tools/_form_engine.py` | Form transformations |
| 4 | `tests/test_form_engine.py` | Form tests |

### Extended Files (cumulative)

- `_composition_engine.py` — HarmonyField, TransitionCritic, EmotionalArcCritic, CrossSectionCritic, GestureTemplates, orchestration taste
- `_agent_os_engine.py` — OutcomeAnalyzer, TechniqueCard, taste_fit computation, technique mining
- `composition.py` — new tools per round
- `agent_os.py` — new tools per round
- `AGENT.md` — updated each round with new tool guidance
- `technique_store.py` — new VALID_TYPES per round

### Tool Count Progression

| Round | New Tools | Total |
|-------|-----------|-------|
| 1 | 3 (harmony_field, transition_analysis, analyze_outcomes) | 189 |
| 2 | 4 (motif_graph, gesture_template, technique_card, section_outcomes) | 193 |
| 3 | 4 (research_technique, deep_research, plan_arrangement, emotional_arc) | 197 |
| 4 | 4 (style_tactics, transform_section, transform_motif, taste_profile) | 201 |

---

## Execution Contract

Each round:
1. Engine code (pure Python, zero I/O)
2. Unit tests (verify before wiring)
3. MCP tool wrappers
4. Contract tests
5. Agent prompt update
6. Tool count housekeeping
7. Full test suite green
8. Git commit + push

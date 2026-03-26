# LivePilot V2

## Deep Product Critique, Research Synthesis, and Roadmap

**Author:** Codex  
**Date:** 2026-03-27  
**Project:** LivePilot for Ableton Live 12  
**Context:** Written after a deep repo audit, architecture review, workflow critique, and external research pass focused on music information retrieval, interactive machine learning, neural audio, co-creative composition systems, and DAW-native artistic workflows.

---

## Executive Summary

LivePilot is already valuable, but not yet for the reason its branding most strongly suggests.

Right now, LivePilot is best understood as:

- a strong AI-readable **Ableton control plane**
- a promising **knowledge layer** for devices, browser access, and session structure
- an early **creative assistant** for deterministic session editing

It is **not yet** a truly advanced tool for:

- deep sound research
- high-level compositional intelligence
- critical listening and mix evaluation
- timbre semantics
- corpus-based exploration
- live interactive co-agency

That gap is the central truth of the project.

The good news is that the direction is fundamentally stronger than most AI music products. LivePilot is attached to an editable musical environment. That gives it a much better long-term foundation than systems that simply generate audio from prompts and leave the user with a static waveform.

The bad news is that the project is beginning to show signs of **scope inflation** and **tool-count drift**. Its original design spec explicitly positioned a smaller tool surface as a way to avoid bloat, while the current README now advertises `178` tools and `17` domains. That shift is meaningful. It suggests the product is expanding breadth faster than it is deepening intelligence.

If LivePilot wants to become a truly world-class system for sound research, AI composition, and interactive artistry, the next phase should not focus on adding more low-level verbs. It should focus on:

1. deeper hearing
2. semantic retrieval
3. corpus intelligence
4. evaluative critique
5. mixed-initiative composition
6. timbre research workflows
7. performance-grade co-agency

The core recommendation of this document is simple:

**LivePilot V2 should evolve from an Ableton command layer into a research-grade musical intelligence layer for editable sessions.**

## Practical Release Reframing

The original V2 strategy is still directionally correct, but it should not be
treated as one monolithic delivery arc.

The better framing is staged, identity-changing releases:

- `V2.0`: listening foundation
- `V2.1`: thin retrieval foundation
- `V2.2`: critique engine
- `V2.x`: corpus workflows, variation, and broader co-creative systems
- `V3 / R&D`: performer-mode co-agency

The practical meaning of that reframing is:

- `V2.0` should ship stronger hearing, snapshot persistence, and section /
  reference analysis before it tries to ship the whole V2 vision
- retrieval should begin in a thin, descriptor-first form rather than as a
  full vector infrastructure project
- critique should follow once listening and minimal retrieval are stable enough
  to support credible evaluation
- performer mode should remain a real opportunity, but not a committed V2
  delivery target until it has its own deeper safety and systems design pass

If only one near-term release ships, it should be this:

- stronger offline analysis
- snapshot persistence
- `analyze_section`
- `analyze_reference_delta`
- enough artifact reuse to make later retrieval possible

That is already enough to change the product's identity.

## One More Constraint: Evolve The Tool Surface Carefully

V2 is not being built in a vacuum.

LivePilot already has a large shipped primitive tool surface, along with
skills, prompts, and habits that may depend on it.

That means the V2 move toward workflows over primitives needs an explicit tool
surface strategy:

- keep V1 primitives stable while V2 workflows are introduced
- guide new users toward workflow tools first
- classify current tools as keep, workflow-wrapped, internal-only, or
  future-deprecate
- avoid pretending the old surface disappears just because a better one is
  being designed

Without this, V2 risks having the right architecture on paper but a confused
public surface in practice.

---

## The Honest Assessment

### What LivePilot Is Good At Today

LivePilot already does several things unusually well.

#### 1. It respects editability

This is one of its biggest strengths. Most AI music systems give the user a finished audio artifact. LivePilot works in Live, where the user still has:

- MIDI
- clips
- devices
- automation
- tracks
- arrangement structure
- undo

That is an enormous strategic advantage.

#### 2. It treats the DAW as a programmable instrument

The architecture is serious:

- Remote Script inside Ableton
- FastMCP server outside Ableton
- strict main-thread handling for LOM operations
- optional M4L bridge for deeper access

This is not a toy architecture. It is the kind of structure that can grow into a durable system.

#### 3. It understands that AI needs environment literacy

The Device Atlas concept is correct in spirit. The system should know:

- what devices exist
- what they are good for
- what parameters matter
- how different tools map to musical intent

This is better than naive prompting and better than hoping a language model remembers every Ableton and user-installed M4L device from prior training.

#### 4. It aims for deterministic tools rather than magical black boxes

This gives the user:

- trust
- repeatability
- inspectability
- safer collaboration

That matters for serious creative work.

#### 5. It has real potential for interactive arts

Because it lives between:

- Ableton
- Max for Live
- live listening
- structured memory
- agent orchestration

it has unusually high potential for:

- audiovisual performance systems
- installations
- adaptive scoring
- intelligent instrument building
- hybrid human/AI live sets

This is one of the most exciting parts of the whole project.

---

### What LivePilot Is Not Good At Yet

This section is the most important one.

#### 1. It does not hear deeply enough

The current analyzer/perception layer is useful, but still shallow.

It hears things like:

- RMS
- peak
- pitch
- key
- band energy
- some spectral descriptors

That is not enough for a truly advanced musical intelligence system.

It still lacks strong, integrated models of:

- groove
- pulse stability
- microtiming
- phrase shape
- form
- section boundaries
- spectral evolution over time
- textural change
- rhythmic salience
- harmonic ambiguity
- timbral similarity
- reference-relative deviation

In other words: it measures signal attributes better than it understands musical behavior.

#### 2. It knows device metadata better than sound

This is the single biggest conceptual limitation.

Much of the project currently thinks in terms of:

- devices
- parameter names
- browser URIs
- note arrays

But musicians and sound artists often think in terms of:

- pressure
- weight
- smear
- bite
- fog
- nearness
- body
- fracture
- spatial tension
- instability
- ritual repetition
- perceived intentionality

LivePilot is still closer to a structured assistant for operating Live than to a system that deeply maps those qualitative intentions to actual sonic outcomes.

#### 3. The memory system is still mostly descriptive, not generative

The current memory design uses:

- tags
- textual summaries
- replay counts
- payload snapshots

That is useful, but it is not yet a real taste model.

A real taste model should understand:

- what transformations succeeded repeatedly
- on what source materials
- in which contexts
- under which stylistic constraints
- with what audible outcomes
- and how the user reacted

That means memory must become:

- perceptual
- comparative
- contextual
- feedback-aware

not just autobiographical.

#### 4. The current generative layer is musically narrower than the branding implies

There are interesting generative tools in the project:

- Euclidean rhythm
- tintinnabuli
- additive processes
- counterpoint
- harmonic transforms

These are intelligent and cool.

But they do not yet amount to a broadly useful composition engine.

They are:

- conceptually rich
- educationally interesting
- sometimes artistically useful

but still partial.

For many real workflows, what matters more is:

- variation under constraint
- phrase continuation
- accompaniment generation
- section contrast
- development over time
- orchestration by role
- tension curves
- motif transformation
- arrangement logic
- style-sensitive groove mutation

That is where the generative system still feels underdeveloped.

#### 5. It lacks a real critical listening loop

The current model mostly acts.

A mature system should do more of this:

- listen
- compare
- diagnose
- propose
- audition
- refine
- justify

The strongest co-creative tools do not simply generate or execute. They critique and adapt.

#### 6. It is growing horizontally faster than vertically

This is the danger zone.

When a system grows by adding many tools and domains, it can create the illusion of capability while actually diluting:

- conceptual clarity
- maintenance quality
- user trust
- product focus

LivePilot is at risk of becoming more impressive to read about than powerful to use.

---

## What Feels Extra

This is the part I would say directly to a founder or research lead.

### 1. The tool-count race feels extra

The original spec framed the product around a smaller, sharper surface:

- `104 tools across 10 domains`

The current README advertises:

- `178 tools across 17 domains`

That is a strategic shift, not a cosmetic one.

It suggests the product has drifted from:

- "a carefully chosen set of production workflows"

toward:

- "a broad set of callable features"

This matters because artists do not primarily experience systems as tool inventories. They experience them as:

- fluency
- timing
- relevance
- surprise
- trust
- taste

If adding tools does not clearly improve those things, the expansion is mostly internal satisfaction, not product value.

### 2. Some symbolic music content feels more like identity than leverage

This includes things like:

- species counterpoint
- Neo-Riemannian navigation
- highly branded harmony features

These are interesting and intellectually attractive.

But for the average serious producer, mix engineer, electronic composer, or installation artist, they are less central than:

- groove control
- arrangement shaping
- transitions
- timbre search
- sound matching
- reference critique
- adaptive variation
- sound-world coherence

These theory tools should exist if they drive a real workflow. They should not dominate the product identity if they are only occasionally relevant.

### 3. The static markdown atlas is too manual as a long-term method

The Device Atlas is conceptually good, but the implementation approach is too human-maintained.

That means:

- it will go stale
- it is labor-intensive
- it does not self-correct
- it is weak on unknown user devices
- it does not learn from actual outputs

Static prose should remain one layer, but not the primary one.

### 4. Some features are one step too far from the user's actual problem

A high-level musician rarely wakes up wanting:

- a named theoretical transform
- a one-off symbolic generator
- a giant list of browser objects

They want:

- "make this section feel like it is inhaling before the drop"
- "find the kick family that matches this bass texture"
- "turn this loop into five related states without losing identity"
- "what is making this mix feel emotionally flat?"
- "find the point where this pad becomes too washed but still intimate"

The more LivePilot aligns with those questions, the more it becomes special.

---

## What Is Strong And Worth Preserving

These are the things I would absolutely keep.

### 1. The core architecture

Keep:

- Remote Script
- MCP server
- M4L bridge
- deterministic command layer
- main-thread discipline

This is the correct technical spine.

### 2. Editable-session-first philosophy

Do not replace the core with prompt-to-audio generation.

Generated audio models can be useful, but they should be:

- satellite tools
- sketch generators
- timbre explorers
- augmentation layers

not the center of the system.

### 3. Device and browser intelligence

Keep the emphasis on:

- exact device identities
- real parameter names
- real load paths
- actual library knowledge

That is powerful.

### 4. Memory as a first-class concept

Keep memory, but deepen it.

### 5. The bridge to Max for Live and interactive workflows

This is one of the best long-term differentiators the project has.

---

## The Right North Star

The wrong north stars are:

- "ChatGPT for Ableton"
- "text-to-song inside Live"
- "the biggest set of Ableton MCP tools"

The right north star is:

**A research-grade musical intelligence layer for editable DAW sessions.**

That means LivePilot should become a system that can:

- understand what is happening musically and sonically
- make high-level creative proposals
- execute them reversibly
- evaluate the result perceptually
- learn the user's taste over time
- support both studio work and live interactive work

This is a much stronger identity.

---

## A Better Conceptual Model For V2

The current knowledge / perception / memory framing is good, but V2 should evolve into five layers:

### 1. Session Control Layer

This is the current deterministic tool layer.

Responsibilities:

- operate Live safely
- expose clips, devices, notes, automation, browser, arrangement
- guarantee reversibility and reliability

### 2. Listening Layer

This should expand dramatically.

Responsibilities:

- hear low-level descriptors
- hear musical structure
- hear transitions
- hear deviations from reference
- hear similarity across sounds and passages

### 3. Semantic Memory Layer

This should unify:

- text summaries
- embeddings
- descriptors
- outcomes
- user preferences
- replay contexts

### 4. Creative Intelligence Layer

This is where the system:

- proposes
- varies
- critiques
- adapts
- orchestrates

### 5. Performance / Interaction Layer

This is the layer for:

- live co-agency
- adaptive systems
- installation logic
- autonomous-but-legible behavior

---

## What V2 Should Add

This section is the core of the roadmap.

### A. Multi-Resolution Listening Engine

This should be the highest-priority addition.

#### Why

Because the current system cannot become truly intelligent until it can hear music on multiple timescales.

#### What to add

##### 1. Event-level listening

- onset detection
- note onset salience
- transient classification
- attack shape
- spectral flux
- per-hit brightness and weight

##### 2. Groove-level listening

- beat tracking
- tempo confidence
- swing estimation
- microtiming deviation
- kick/snare/hat role inference
- rhythmic density maps

##### 3. Phrase-level listening

- phrase boundary detection
- melodic contour shape
- harmonic rhythm
- tension/release estimation
- energy arcs

##### 4. Section-level listening

- intro/verse/drop/break/outro clustering
- arrangement similarity
- section contrast
- section transition quality

##### 5. Mix-level listening

- spectral balance over time
- masking likelihood
- mono compatibility
- width profile
- loudness contour
- reference-relative differences

#### Suggested technical stack

- **librosa** as the default low-friction analysis backend
- **Essentia** as an optional higher-power backend for rhythm / tonal / MIR-heavy analysis  
  [https://essentia.upf.edu/documentation.html](https://essentia.upf.edu/documentation.html)
- **FluCoMa** in Max for interactive descriptor extraction and corpus work  
  [https://learn.flucoma.org/getting-started/](https://learn.flucoma.org/getting-started/)
- optional custom offline analysis jobs for deeper passes on stems, references, and exports

#### What this unlocks

- "find the bar where the groove starts to drag"
- "make the pre-drop energy rise more clearly"
- "compare the spectral movement of this chorus to the reference"
- "show me why this loop feels static"

---

### B. Semantic Audio Memory

The current memory model is not enough.

V2 memory should contain at least five kinds of data:

#### 1. Symbolic structure

- notes
- timing
- device chains
- automation shapes
- arrangement sections

#### 2. Perceptual descriptors

- loudness
- spectral shape
- temporal density
- brightness
- roughness
- harmonicity
- onset rate
- motion

#### 3. Embeddings

- audio embeddings
- clip embeddings
- reference embeddings
- optionally text-audio shared embeddings

#### 4. Outcome context

- what task the user was solving
- what source material was used
- what changed
- what the audible result was

#### 5. Feedback signals

- accepted / rejected
- revised after suggestion
- replayed later
- tagged as favorite
- used in finished work

#### Why this matters

This turns memory from:

- "what happened"

into:

- "what tends to work for this user in this context"

#### What to build

- a local similarity layer for clips, assets, and techniques
- optional embedding storage behind a backend abstraction
- perceptual fingerprints for clips and device states
- technique records that link text, signal features, and outcomes

#### What this unlocks

- "find three old chains that gave me this kind of pressure"
- "retrieve loops similar in texture but slower and darker"
- "what mix moves have I historically liked on fragile vocals"

---

### C. Corpus Lab

This is one of the highest-leverage additions for sound researchers and artists.

#### The idea

LivePilot should not only manipulate clips in session. It should be able to build and explore **corpora** of:

- samples
- field recordings
- stems
- user renders
- presets
- device output captures

#### Core operations

- analyze corpus
- extract descriptors
- cluster items
- map them in 2D / latent space
- search by sound
- search by text
- search by example
- segment and slice automatically
- audition nearest neighbors
- build transformation sets

#### Why this matters artistically

This is where the system starts to feel like a real laboratory rather than an automation shell.

For sound artists, this is huge.

Examples:

- cluster all your metal scrapes, breaths, and room tones by texture
- find "the next nearest" sound that is harsher but not brighter
- build a family of related impacts for performance mapping
- discover hidden continuity across a large archive

#### Recommended integration

- FluCoMa descriptor workflows in Max
- offline Python analysis for embeddings and indexing
- Live browser integration for loading results directly back into the set

---

### D. Reference And Critique Engine

This is one of the most musically valuable missing pieces.

#### Problem

Many users do not need more generation. They need better diagnosis.

#### What this engine should do

- compare current mix to reference by section
- compare current loop to prior saved versions
- identify where perceived energy diverges
- detect probable masking
- detect over-brightness or under-articulation
- identify section sameness
- identify timbral inconsistency across arrangement

#### A better response style

Instead of saying:

- "your RMS is X"

it should say:

- "the chorus feels flatter than the reference because your upper-mid attack rises less while width and low-mid density increase at the same moment"

#### Outputs

- diagnosis
- confidence
- optional actions
- audition plan

#### Why this matters

This is the path from assistant to trusted collaborator.

---

### E. Timbre Intelligence Stack

This is where LivePilot could become genuinely advanced.

There are at least four useful levels here.

#### Level 1: Descriptor-based timbre reasoning

This is classical MIR:

- brightness
- noisiness
- harmonicity
- spectral centroid
- flatness
- attack sharpness
- temporal modulation

Useful, but limited.

#### Level 2: Embedding-based timbre similarity

Use audio embeddings to search and compare:

- sounds
- presets
- rendered chains
- transformed variants

This is much closer to how artists work.

#### Level 3: Text-guided timbre mapping

This is where CLAP-style systems become useful.

They can help map words like:

- cloudy
- brittle
- intimate
- cavernous
- scraped
- devotional
- plastic

into retrieval targets or parameter search directions.

Relevant references:

- CLAP  
  [https://arxiv.org/abs/2206.04769](https://arxiv.org/abs/2206.04769)
- Text2FX  
  [https://arxiv.org/abs/2409.18847](https://arxiv.org/abs/2409.18847)

#### Level 4: Neural timbre transformation

This is where systems like RAVE and DDSP matter.

These models are exciting because they expose:

- controllable timbre transfer
- latent navigation
- style transfer
- neural resynthesis
- differentiable audio shaping

Relevant references:

- RAVE  
  [https://github.com/acids-ircam/RAVE](https://github.com/acids-ircam/RAVE)
- DDSP  
  [https://research.google/pubs/ddsp-differentiable-digital-signal-processing/](https://research.google/pubs/ddsp-differentiable-digital-signal-processing/)

#### Recommended V2 position

Do not make neural timbre models the core.

Use them as:

- optional advanced modules
- timbre lab tools
- artist-grade experimental engines

---

### F. Mixed-Initiative Composition Engine

This is where composition becomes more serious.

#### Current state

The current symbolic/generative tools are interesting but fragmented.

#### What V2 should support instead

##### 1. Continuation under constraint

- continue this melody but keep the same emotional contour
- continue this bassline with more tension
- extend this section without changing its identity too much

##### 2. Variation families

- generate 5 related hat patterns
- produce 3 breakdown variants
- create a less busy twin of this groove

##### 3. Role-aware composition

Work by musical role, not only notes:

- kick role
- bass role
- harmonic bed
- lead contour
- percussive glitter
- transitional noise

##### 4. Section-aware planning

- intro
- build
- drop
- release
- aftermath

##### 5. Constraint-based orchestration

Examples:

- keep the midrange open for vocals
- keep bass monophonic
- do not add more note density, only timbral variation

#### Better model inspirations

The most useful systems here are not necessarily giant prompt-to-audio models.

More relevant inspirations:

- Bach Doodle / Coconet for approachable constrained harmonization  
  [https://arxiv.org/abs/1907.06637](https://arxiv.org/abs/1907.06637)
- mixed-initiative composition systems like TOMI  
  [https://arxiv.org/abs/2506.23094](https://arxiv.org/abs/2506.23094)
- performance-oriented symbolic systems such as Notochord  
  [https://arxiv.org/abs/2403.12000](https://arxiv.org/abs/2403.12000)

#### What to deprioritize

Do not over-invest in obscure theory transforms unless they clearly serve these higher-order workflows.

---

### G. Live Performance And Installation Mode

This is one of the most exciting strategic opportunities.

V2 should support a distinct mode aimed at:

- interactive artists
- performers
- installation makers
- audiovisual system builders

#### This mode should support

- agent behavior constrained by performance rules
- adaptive response to incoming audio
- adaptive response to performer gestures
- cue-based transitions
- controlled autonomous variation
- legible co-agency

#### Key principle

In live work, intelligence is not enough. **Legibility** matters.

The audience and performer need to be able to feel:

- who is driving
- when the system is listening
- when it is proposing
- when it is taking initiative
- when it is restrained

#### Desired design features

- explicit behavioral scenes
- probability ceilings
- role boundaries
- panic / freeze / mute / rollback controls
- visible internal state summaries

#### Why this matters

This is how LivePilot becomes more than a studio assistant. It becomes an artistic instrument.

---

## What I Would Cut Or Deprioritize

If V2 wants to become stronger, it must subtract as well as add.

### Deprioritize

- adding many more low-level tools
- expanding symbolic novelty features without clear workflows
- static prose-heavy atlas growth without self-updating mechanisms
- branding around academic theory features unless they anchor repeat usage
- one-off gimmick generators

### Keep but reframe

- theory tools as optional composition aids
- atlas as one layer of a larger knowledge system
- memory summaries as human-readable annotations, not the main intelligence substrate

### Cut if maintenance gets expensive

- redundant low-level wrappers whose value is only completeness
- niche tools that do not support larger workflows

---

## A Better Workflow Model

The current system is still too command-centric.

I would redesign the agent around a repeated loop:

1. **Hear**  
   Analyze the current material
2. **Diagnose**  
   Explain what is happening
3. **Propose**  
   Offer 2-4 meaningful directions
4. **Act**  
   Make reversible changes
5. **Audition**  
   Compare before and after
6. **Learn**  
   Store what worked

This loop should be the center of the user experience.

---

## Proposed V2 Product Modes

### 1. Lab

For:

- sound research
- descriptor analysis
- corpus exploration
- retrieval
- timbre comparison

### 2. Composer

For:

- sketch generation
- continuation
- variation
- harmony and role planning
- arrangement logic

### 3. Producer

For:

- device selection
- chain construction
- reference critique
- transition design
- mix problem solving

### 4. Performer

For:

- live co-agency
- performance adaptation
- installation behavior
- real-time cue-driven transformation

These modes should share the same infrastructure but differ in:

- tools surfaced
- response style
- initiative level
- safety constraints

---

## Recommended Technical Architecture For V2

### Keep In Remote Script

Only what must stay close to Ableton:

- session state access
- clip and note mutation
- arrangement and automation operations
- browser and device operations
- reliable transport and undoable edits

### Keep In M4L / Max

Real-time and artistic signal-side work:

- streaming analysis
- descriptor extraction
- corpus preview interfaces
- gesture mapping
- interactive ML hooks
- performance logic

### Expand In Python

This should become the real intelligence layer:

- MIR pipelines
- embedding extraction
- retrieval engines
- memory indexing
- offline analysis jobs
- critique engines
- planning and adaptation logic

### Optional Model Layer

Separate optional modules for:

- audio embeddings
- symbolic continuation
- timbre models
- text-guided FX search
- arrangement suggestion

This layer should be modular and not block the core product.

---

## Research Directions Worth Pursuing

### 1. MIR and musical structure

Use research and tools that improve:

- beat tracking
- segmentation
- chord estimation
- section boundaries
- novelty curves
- recurrence analysis
- tempo confidence
- groove descriptors

### 2. Text-audio alignment

Use shared embedding spaces carefully for:

- search
- retrieval
- rough semantic guidance
- timbral target matching

Do not oversell them as perfect musical understanding.

### 3. Interactive machine learning

This is especially relevant for Max and performance systems.

The project should learn from the culture around:

- Wekinator-style rapid interactive ML
- FluCoMa workflows
- performer-in-the-loop training

### 4. Neural audio as instrument augmentation

This should be used where it is most artistically fruitful:

- resynthesis
- timbre transfer
- latent interpolation
- style-conditioned transformation

### 5. Mixed-initiative composition

This is less about “generate more” and more about:

- constraint satisfaction
- option spaces
- partial completions
- user steering

---

## What “Super Capable” Should Mean For This Product

If I were defining a truly advanced version of LivePilot for a sound researcher, high-level musician, and interactive artist, I would want these capabilities:

### For Sound Research

- search your archive by sonic similarity
- cluster sounds by behavior, not only filename
- compare device chains by actual output
- map parameter moves to perceived change
- audition transformation paths
- discover hidden families in your material

### For Composition

- continue and vary phrases intelligently
- orchestrate by role and density
- preserve identity while transforming
- shape sections by tension curve
- suggest contrast strategies
- create development, not just more notes

### For Production

- diagnose stagnation
- diagnose masking
- compare sections to references
- generate focused mix experiments
- keep stylistic continuity across a project

### For Live / Installation Work

- act under constraints
- respond to the room or performer
- behave legibly
- support intentional co-agency
- remain interruptible and safe

That is the bar.

---

## A Practical V2 Roadmap

This is the build order I would recommend.

### Phase 0: Refocus The Product

**Goal:** reduce drift and clarify the mission.

#### Deliverables

- define V2 north star
- identify low-value tools to freeze
- group current tools into high-level workflows
- stop expanding tool count by default

#### Success metric

- the product description becomes clearer and less tool-count centric

---

### Phase 1: Listening Upgrade

**Goal:** give the system better ears.

#### Deliverables

- offline MIR analysis jobs for clips, stems, and references
- stronger section and groove descriptors
- reference-comparison primitives
- richer spectral trajectory analysis

#### Suggested stack

- librosa by default
- optional Essentia backend
- existing M4L bridge for real-time metrics

#### Success metric

- the agent can produce musically useful diagnoses, not only signal readouts

---

### Phase 2: Semantic Memory Upgrade

**Goal:** turn memory into an operational taste and retrieval system.

#### Deliverables

- descriptor vectors stored with techniques
- audio/item embeddings
- local similarity retrieval
- user feedback capture
- outcome-aware technique records

#### Success metric

- the agent can retrieve prior work by sound, role, or behavior rather than only tags

---

### Phase 3: Corpus Lab

**Goal:** make LivePilot valuable for sound researchers and sonic explorers.

#### Deliverables

- corpus ingestion
- descriptor extraction
- clustering
- nearest-neighbor search
- preview and load workflows back into Live

#### Success metric

- a user can explore a large personal archive as a navigable sonic field

---

### Phase 4: Critique And Reference Engine

**Goal:** build trust through evaluative intelligence.

#### Deliverables

- section-to-reference comparison
- mix issue diagnosis
- transition weakness detection
- energy-arc comparison
- concise action recommendations

#### Success metric

- the agent reliably helps improve a track through critique, not only action

---

### Phase 5: Mixed-Initiative Composition

**Goal:** make the system a real compositional collaborator.

#### Deliverables

- continuation under constraint
- variation families
- section-aware development
- role-aware orchestration
- style-sensitive regeneration

#### Success metric

- users prefer the system for development and ideation, not only for control and recall

---

### Phase 6: Timbre Lab And Neural Modules

**Goal:** unlock advanced sound research and artistic experimentation.

#### Deliverables

- embedding-based timbre search
- text-guided timbre retrieval
- optional RAVE/DDSP workflows
- audio-to-audio transformation experiments

#### Success metric

- users can navigate and transform timbre as a first-class creative space

---

### Phase 7: Performance / Installation Mode

**Goal:** transform LivePilot into an interactive artistic instrument.

#### Deliverables

- behavior states
- constrained autonomy
- co-agency visibility
- performance-safe controls
- cue-based scene transitions

#### Success metric

- stable, legible live behavior under performance conditions

---

## Concrete Workflow Concepts Worth Building

These are the kinds of experiences that would make LivePilot feel advanced.

### 1. Sonic Neighbor Search

User says:

> Find five sounds in my archive that feel like this one, but rougher and less bright.

System does:

- analyze example
- retrieve nearest neighbors
- re-rank by descriptor targets
- audition candidates
- load selected candidate into Live

### 2. Section Contrast Doctor

User says:

> Why does the drop not feel bigger?

System does:

- compare pre-drop vs drop energy profile
- identify what changed and what did not
- diagnose missing contrast dimensions
- propose three actionable fixes

### 3. Device Chain Family Builder

User says:

> Give me four related distortion chains for this bass, from polite to violent.

System does:

- analyze source
- choose device families by known behavior
- render or estimate resulting trajectories
- present ordered ladder of options

### 4. Phrase Variation Engine

User says:

> Keep the identity of this loop, but make it evolve for another 32 bars.

System does:

- identify core motifs
- preserve role structure
- vary density, articulation, and timbre over time
- propose staged development

### 5. Corpus Morph Map

User says:

> Build a map between my bowed metal, whispers, and modular noise recordings.

System does:

- analyze corpus
- cluster descriptors and embeddings
- expose neighboring zones
- suggest transition paths and hybrid families

This is the kind of feature that could make the project artistically unique.

---

## Evaluation: How To Know V2 Is Actually Better

Do not judge success by:

- total tool count
- README scope
- number of named domains

Judge success by:

### 1. Time-to-useful-result

Can a user get to a meaningful sonic outcome faster?

### 2. Quality of diagnosis

Does the agent explain problems in musically convincing terms?

### 3. Retrieval relevance

Can it find the right sounds, chains, or references?

### 4. Variation quality

Does it produce useful related options rather than random alternatives?

### 5. Trust

Do users feel the system is hearing the same thing they are hearing?

### 6. Artistic surprise

Does it create discoveries, not just efficiencies?

### 7. Legibility in live contexts

Can performers understand what the system is doing and why?

---

## Risks To Watch

### 1. Bloat disguised as ambition

The project must avoid confusing:

- more endpoints

with:

- more intelligence

### 2. Research theater

Using terms like:

- embeddings
- latent space
- neural audio
- MIR

is not enough. They need to improve real workflows.

### 3. Overfitting to prose

Too much knowledge stored as text will eventually limit the system.

### 4. Underestimating retrieval

Retrieval is one of the most powerful capabilities available here. It should be central.

### 5. Live-performance fragility

Anything intended for performance needs stricter behavior modeling and safety constraints than studio-only features.

---

## Final Opinion

LivePilot is already meaningful.

It is not just another AI music project, because it is built around:

- editability
- reversibility
- environment knowledge
- deterministic control
- integration with a real artistic tool

That is rare and valuable.

But it is still closer to:

- an advanced Ableton operation layer

than to:

- a fully realized musical intelligence system

The next leap will not come from adding more commands.

It will come from making the system:

- hear better
- remember better
- retrieve better
- critique better
- co-create better

If that happens, LivePilot could become a genuinely important system for:

- producers
- composers
- sonic researchers
- live performers
- installation artists

If it does not happen, the project may remain impressive but slightly overextended: strong on scope, weaker on depth.

My strongest recommendation is this:

**Build V2 around hearing, retrieval, critique, and co-agency.**

That is where the project can become exceptional.

---

## Research Anchors

These are the main references that matter for the direction above.

### Ableton / Max

- Ableton Live 12 manual: Editing MIDI / MIDI Tools  
  [https://www.ableton.com/en/live-manual/12/editing-midi/](https://www.ableton.com/en/live-manual/12/editing-midi/)
- Ableton help: controlling Live using Max for Live  
  [https://help.ableton.com/hc/en-us/articles/5402681764242-Controlling-Live-using-Max-for-Live](https://help.ableton.com/hc/en-us/articles/5402681764242-Controlling-Live-using-Max-for-Live)
- Ableton help: Max for Live bundled in Live  
  [https://help.ableton.com/hc/en-us/articles/360000036850-Max-for-Live-bundled-in-Live](https://help.ableton.com/hc/en-us/articles/360000036850-Max-for-Live-bundled-in-Live)

### MIR / Corpus / Interactive ML

- FluCoMa getting started  
  [https://learn.flucoma.org/getting-started/](https://learn.flucoma.org/getting-started/)
- Essentia documentation  
  [https://essentia.upf.edu/documentation.html](https://essentia.upf.edu/documentation.html)

### Text-Audio And Effects

- CLAP: Learning Audio Concepts from Natural Language Supervision  
  [https://arxiv.org/abs/2206.04769](https://arxiv.org/abs/2206.04769)
- Text2FX: Harnessing CLAP Embeddings for Text-Guided Audio Effects  
  [https://arxiv.org/abs/2409.18847](https://arxiv.org/abs/2409.18847)

### Neural Audio / Timbre

- RAVE official repository  
  [https://github.com/acids-ircam/RAVE](https://github.com/acids-ircam/RAVE)
- DDSP: Differentiable Digital Signal Processing  
  [https://research.google/pubs/ddsp-differentiable-digital-signal-processing/](https://research.google/pubs/ddsp-differentiable-digital-signal-processing/)

### Generative Composition / Mixed Initiative

- Bach Doodle / Coconet  
  [https://arxiv.org/abs/1907.06637](https://arxiv.org/abs/1907.06637)
- MusicGen  
  [https://arxiv.org/abs/2306.05284](https://arxiv.org/abs/2306.05284)
- MusicLM  
  [https://research.google/pubs/musiclm-generating-music-from-text/](https://research.google/pubs/musiclm-generating-music-from-text/)
- TOMI  
  [https://arxiv.org/abs/2506.23094](https://arxiv.org/abs/2506.23094)
- Notochord  
  [https://arxiv.org/abs/2403.12000](https://arxiv.org/abs/2403.12000)

---

## Repo Context Notes

Relevant local design documents reviewed during this synthesis:

- [LivePilot design spec](../specs/2026-03-17-livepilot-design.md)
- [M4L bridge spec](../specs/2026-03-18-m4l-bridge-spec.md)
- [Device Atlas design](../specs/2026-03-18-device-atlas-design.md)
- [Technique Memory design](../specs/2026-03-18-technique-memory-system-design.md)

---

## Closing Line

LivePilot does not need to become bigger.

It needs to become deeper.

# Research Engine v1

Status: proposal

Audience: research, runtime, docs, plugin-intelligence, memory, and evaluation owners

Purpose: define the concrete implementation plan for LivePilot's research subsystem so research becomes actionable production intelligence instead of link collection.

## 1. Product Role

Research Engine should activate when the user explicitly asks for research or when the system lacks enough local knowledge to act confidently.

It should answer questions like:

- what techniques fit this plugin
- how does this style usually handle transitions
- what do trusted sources recommend for this problem
- which of those tactics actually fit this session

## 2. Design Principle

Research is provider-aware.

The engine should never assume open-web access.

Provider ladder:

1. session evidence
2. local docs/specs
3. memory and technique cards
4. user-supplied references
5. structured connectors
6. web

## 3. Operating Modes

- `none`
- `targeted`
- `deep`
- `background_mining`

### 3.1 Targeted

Used for:

- one device question
- one style question
- one production problem

### 3.2 Deep

Used for:

- multi-source synthesis
- unfamiliar plugin ecosystems
- explicit "go deep" user requests

### 3.3 Background Mining

Used outside the live critical path to enrich tactic libraries.

## 4. Output Units

Research Engine should output:

- `technique_cards`
- `style_tactic_cards`
- `plugin_tactic_cards`
- `failure_warnings`

Not:

- raw scraped note dumps
- giant source summaries with no action mapping

## 5. Data Contract

```json
{
  "research_result": {
    "question": "How should this plugin be used for moving percussion without losing groove?",
    "mode": "targeted",
    "providers_used": ["local_docs", "memory", "web"],
    "cards": [
      {
        "type": "plugin_tactic_card",
        "name": "subtle unsynced motion",
        "fit_score": 0.84,
        "risk": "low"
      }
    ],
    "warnings": ["avoid widening the center percussion anchor"],
    "confidence": 0.76
  }
}
```

## 6. Module Layout

- `mcp_server/research/models.py`
- `mcp_server/research/provider_router.py`
- `mcp_server/research/extractors.py`
- `mcp_server/research/card_builder.py`
- `mcp_server/research/ranker.py`

## 7. Integration

### 7.1 Capability State

Determines what providers are even available.

### 7.2 Memory Fabric

Supplies existing tactic cards and receives validated promotions later.

### 7.3 Engines

Composition, Mix, Sound Design, and Reference can all request research results, but they should receive cards, not raw provider payloads.

## 8. Evaluation

Research should itself be measured.

Track:

- whether the card was actually applied
- whether the resulting move was kept
- whether the user liked the researched direction

This lets the system learn which sources and tactic styles are actually useful.

## 9. Build Order

1. Implement provider router and provider ladder contracts.
2. Add targeted research output as tactic cards.
3. Add deep-research synthesis path.
4. Add research-outcome feedback into memory.

## 10. Exit Criteria

Research Engine v1 is done when:

- the system can perform useful research without assuming web access
- research outputs become ranked tactic cards
- engines can consume research results without bespoke parsing
- useful researched tactics can be promoted into local knowledge after validation

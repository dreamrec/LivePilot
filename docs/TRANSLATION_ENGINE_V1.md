# Translation Engine v1

Status: proposal

Audience: mix, mastering, evaluation, and playback-robustness owners

Purpose: define the subsystem that helps LivePilot reason about how a track survives across playback contexts.

## 1. Product Role

Translation Engine is not "AI mastering."

Its role is to answer:

- will this still work in mono
- does the low end survive small speakers
- is the vocal/front element still present on headphones
- is the brightness harsh on earbuds
- is the center collapsing under width moves

## 2. Scope

v1 should focus on diagnosis and validation, not autonomous final mastering chains.

Primary goals:

- playback robustness
- mono compatibility
- low-end stability
- harshness risk
- front-element preservation

## 3. Inputs

Use:

- mix state
- spectrum summaries
- RMS/peak/loudness metrics
- width-related metrics when implemented
- reference comparisons
- accepted taste priors

## 4. Critics v1

Implement:

- `mono_collapse_critic`
- `small_speaker_critic`
- `harshness_critic`
- `low_end_instability_critic`
- `front_element_presence_critic`

## 5. Recommended Runtime Surface

Suggested modules:

- `mcp_server/translation/models.py`
- `mcp_server/translation/critics.py`
- `mcp_server/translation/evaluator.py`
- `mcp_server/translation/reports.py`

## 6. Evaluation Contract

Outputs should be explicit:

- robust
- fragile
- likely_issue_domains
- suggested corrective move classes

## 7. Build Order

1. Implement translation report contract.
2. Add critics using available metrics.
3. Add reference-relative translation hints.
4. Add hooks into Mix Engine keep/undo loop.

## 8. Exit Criteria

Translation Engine v1 is done when:

- the system can explain likely playback risks clearly
- mix moves can be validated against playback robustness goals
- it meaningfully reduces false-confidence width or loudness decisions

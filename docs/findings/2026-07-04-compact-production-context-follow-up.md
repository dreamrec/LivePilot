# Compact Production Context Follow-Up

## Problem

`get_production_context` is the correct primary read for Codex cockpit work, but
its default payload is intentionally rich: session summary, target tracks,
track intent, layers, briefs, orchestration state, memory health, and route
classification. That is useful when an agent is starting a real production
turn, but it is heavier than needed for quick status checks, queue polling, or
handoff confirmation.

The cockpit hardening work added a compact `/api/session` browser endpoint for
UI readiness, but model-facing MCP reads still have only the full production
context shape.

## Future Shape

Add one compact model-facing read path. Preferred option:

```python
get_production_context(
    request_text="",
    include_history=False,
    detail="full",  # "full" | "summary"
    include_annotations=True,
    include_orchestration=True,
    warnings_limit=25,
)
```

Alternative if the parameterized contract gets too crowded:

```python
get_cockpit_summary(request_text="")
```

The compact shape should include:

- project id and project identity;
- selected target mode, target label, selected track indices/names, and section;
- lane, output mode, evidence budget, and protect flags;
- memory-health counts only;
- queue counts only;
- analyzer status and `judgment_only` flag;
- current completion contract string.

It should omit full annotations, full layer member metadata, full brief rows,
full proposal/job rows, and warning lists beyond the configured limit.

## Constraints

- Keep `get_production_context` backward-compatible: default remains full.
- Do not add another public tool unless the parameterized version becomes
  unclear for agents.
- If a new tool is added, update the public tool count, tool catalog, metadata,
  and plugin docs through the normal `sync_metadata.py` flow.
- Compact reads must still stamp the brief reader, because Codex has read the
  current working state.
- Compact reads are read-only and must not bump `project_revision`.

## Acceptance

- `detail="summary"` returns a bounded payload for a large session.
- A summary read is sufficient to answer "what am I focused on?" and "what
  should I do next?" without pulling full annotation or queue rows.
- Existing full-context tests keep passing unchanged.

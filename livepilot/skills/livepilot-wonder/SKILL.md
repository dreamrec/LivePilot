---
name: livepilot-wonder
description: >
  This skill should be used when the user asks to "surprise me",
  "make it magical", "I'm stuck", "give me options", "take it somewhere",
  or when stuckness confidence is high. Provides the Wonder Mode
  stuck-rescue workflow with honest variant labeling and preview-first UX.
---

# Wonder Mode — Stuck-Rescue Workflow

Wonder Mode is a **preview-first stuck-rescue workflow**. It diagnoses
why a session is stuck, generates genuinely distinct executable options,
and lets the user preview, compare, and commit.

## When to Trigger

- User says "I'm stuck", "surprise me", "make it magical", "give me options"
- `detect_stuckness` confidence > 0.5
- 3+ consecutive undos in action ledger
- Multiple plausible next moves with no clear winner
- **`livepilot-creative-director` delegates divergence to Wonder** (first-pass creative intent, not only rescue)

## Two contexts — Stuck-Rescue vs Creative-Director Divergence

Wonder Mode now serves two callers:

1. **Stuck-rescue** (original): a specific session is stuck and needs
   rescue. The "fewer than 3 variants is correct" honesty rule applies —
   you are not obligated to fabricate options that don't exist.

2. **Creative-director first-pass**: the director is running standard
   divergence before any commit. Here, actively WIDEN across `move.family`
   before accepting fewer than 3 variants. Only fall back after honestly
   re-reading concept packets, anti-preferences, and recent memory. The
   context comes in via the `wonder_session_id` metadata or the caller's
   explicit framing.

## When NOT to Trigger

- Exact operational requests ("set track 3 volume to -6dB")
- Narrow deterministic edits ("quantize this clip")
- Performance-safe-only context (unless explicitly requested)

## The Workflow

1. `enter_wonder_mode` — get diagnosis + 1-3 variants
2. Explain the diagnosis in **musical language**, not tool language
3. Present variants honestly:
   - Executable variants: can be previewed and committed
   - Analytical variants (`analytical_only: true`): directional ideas only
4. `create_preview_set` with `wonder_session_id` for executable variants
5. `render_preview_variant` for each executable variant
6. `compare_preview_variants` — present recommendation with reasons
7. User chooses:
   - `commit_preview_variant` — applies the variant, records outcome
   - `discard_wonder_session` — rejects all, keeps creative thread open

## Honesty Rules

- **Never describe an analytical variant as previewable**
- **Never fabricate distinctness** by relabeling the same move — and
  specifically, two variants with the same `move.family` are not distinct
- **Fewer than 3 variants is correct** when fewer distinct moves exist —
  but on creative-director first-pass, widen across `move.family` values
  FIRST before accepting that conclusion (see `livepilot-creative-director`
  references/move-family-diversity-rule.md)
- 1 executable + 2 analytical is an honest, useful result
- The `variant_count_actual` field tells you how many are real

## Presenting Results

For each variant, explain:
- What it changes (in musical terms)
- What it preserves (sacred elements)
- Why it matters for this specific session
- Whether it's executable or analytical-only

For the recommendation, explain:
- Why this one over the others
- What risk it introduces
- What sacred elements it preserves

## Creative Intelligence (consult before generating variants)

Wonder Mode should produce musically interesting results, not just technically correct ones. Before generating or applying any variant, read the shared device-knowledge references (they live in the `livepilot-core` skill, not in this one):

1. `livepilot-core/references/device-knowledge/automation-as-music.md` — automation shapes and macro gestures
2. `livepilot-core/references/device-knowledge/creative-thinking.md` — emotional-to-technical mapping
3. `livepilot-core/references/device-knowledge/chains-genre.md` — if the session has a genre identity

When reviewing Wonder variants, aim for musical depth:
- **Filter arcs** — evolving filter across sections adds movement
- **Space arcs** — reverb/delay sends breathing with density
- **Micro-modulation** — subtle LFOs on sustained sounds
- **Macro gestures** — coordinated multi-parameter moves at transitions

Note: these are agent-level guidelines, not enforced by the Wonder engine.
The engine generates variants from semantic moves; the agent adds musical polish.

# Sound Design Critics Reference

The sound-design critics inspect visible patch topology and declared goals.
They do not measure spectral flux, modulation depth, or musical quality.
Each issue includes issue_type, critic, severity, confidence, affected_blocks,
evidence, recommended_moves, evidence_basis="topology_heuristic", and
measured=false. Severity ranks a structural hypothesis, not an audio defect.

## Explicit intent

analyze_sound_design, get_sound_design_issues, and plan_sound_design_move
accept optional goal dimensions in -1..1. For example, goal={"movement":0.5,
"brightness":-0.2} requests more movement and less brightness. Omitted
means no requested change. Do not impose movement, saturation, filtering,
or greater patch complexity when the user did not request them.

## static_timbre

When movement or instability is explicitly requested and no dedicated
modulation source appears in the inspected blocks, the critic may emit one
qualified advisory at confidence 0.35. It asks the agent to check existing
automation, sample movement, and internal routing before adding modulation.
Opaque devices suppress this inference because their hidden modulation is
unknown. A visible LFO or envelope indicates structural availability; it
does not prove that modulation is active or audible.

No default no_modulation_sources penalty is emitted. Absence of an LFO does
not establish audible stasis, and a deliberately static part is valid.

## weak_identity and modulation_flatness

These compatibility hooks emit no findings. Block count and absence of
filters/saturation cannot establish weak identity. The topology model does
not expose the modulation ranges or audio evidence needed to judge flatness.
The static critic above handles explicit movement requests without duplicate
penalties.

## masking_role and layer_overlap

These critics compare declared layer roles and track assignments. A shared
track can flag a potential role overlap, but it does not prove frequency
masking or a bad arrangement. Check actual audio and the musical brief.

## corpus

Corpus recipes can suggest opportunities that relate to an explicit timbral
goal. Their device suggestions are optional techniques, not required effects
or proof that the current chain is deficient.

## Verify creative benefit

Inspect supported parameters and the current routing before changing sound.
For an audible comparison, capture the same musical passage before and after
and use listen_ab. Keep level changes visible, and let the user choose what
serves the piece. A technical measurement and an artistic preference are
different kinds of evidence.

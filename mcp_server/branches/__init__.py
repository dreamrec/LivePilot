"""Branch-native types — the shared substrate for Wonder, Preview Studio,
Experiment, and future producers (synthesis_brain, composer).

A BranchSeed is a producer-emitted creative intent (pre-compilation).
A CompiledBranch pairs a seed with a concrete plan ready for the execution
router. compiled_plan=None ⇒ analytical-only (directional suggestion).

This module is pure types + factory helpers. No I/O, no side effects, no
imports from other mcp_server subsystems.
"""

from .types import (
    BranchSeed,
    CompiledBranch,
    BranchSource,
    RiskLabel,
    NoveltyLabel,
    PRODUCER_PAYLOAD_SCHEMA_VERSION,
    seed_from_move_id,
    freeform_seed,
    analytical_seed,
)

__all__ = [
    "BranchSeed",
    "CompiledBranch",
    "BranchSource",
    "RiskLabel",
    "NoveltyLabel",
    "PRODUCER_PAYLOAD_SCHEMA_VERSION",
    "seed_from_move_id",
    "freeform_seed",
    "analytical_seed",
]

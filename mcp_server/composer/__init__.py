"""Composer Engine — auto-composition from text prompts via Splice + Sample Engine.

PR11 adds branch_producer.propose_composer_branches() for emitting
multiple section-hypothesis BranchSeeds alongside the existing
single-plan compose() entry point.
"""

from .branch_producer import propose_composer_branches, escalate_composer_branch

__all__ = ["propose_composer_branches", "escalate_composer_branch"]

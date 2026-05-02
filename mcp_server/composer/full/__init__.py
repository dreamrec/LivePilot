"""Full compose mode — currently deterministic engine; will become two-phase
LLM-creative in v1.24 Phase 3 (BUG-FULL-MODE-18 fix).

Phase 1 of v1.24 just moves the existing code here without behavior change.
"""
from .engine import ComposerEngine, CompositionResult
from .apply import apply_full_plan
from .brief_builder import build_full_brief

__all__ = ["ComposerEngine", "CompositionResult", "apply_full_plan", "build_full_brief"]

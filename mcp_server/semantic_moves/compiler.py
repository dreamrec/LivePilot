"""Semantic move compiler — resolves intents to concrete tool call sequences.

The compiler takes a SemanticMove + SessionKernel and produces a CompiledPlan:
a list of concrete, parameterized tool calls ready for execution.

Each move family registers a compiler function. The generic compile() dispatcher
routes to the right family compiler based on the move's family field.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from .models import SemanticMove


# ── Compiled plan types ──────────────────────────────────────────────────────

@dataclass
class CompiledStep:
    """A single executable tool call with resolved parameters."""
    tool: str                    # MCP tool name, e.g. "set_track_volume"
    params: dict                 # Concrete params, e.g. {"track_index": 0, "volume": 0.72}
    description: str             # Human-readable, e.g. "Push Drums from 0.65 → 0.72"
    verify_after: bool = True    # Whether to check meters after this step

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "params": self.params,
            "description": self.description,
            "verify_after": self.verify_after,
        }


@dataclass
class CompiledPlan:
    """The output of compilation — ready for execution or presentation."""
    move_id: str
    intent: str
    steps: list[CompiledStep] = field(default_factory=list)
    before_reads: list[dict] = field(default_factory=list)
    after_reads: list[dict] = field(default_factory=list)
    risk_level: str = "low"
    summary: str = ""
    requires_approval: bool = True
    warnings: list[str] = field(default_factory=list)

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def executable(self) -> bool:
        """A plan is executable if it has at least one step."""
        return len(self.steps) > 0

    def to_dict(self) -> dict:
        return {
            "move_id": self.move_id,
            "intent": self.intent,
            "steps": [s.to_dict() for s in self.steps],
            "step_count": self.step_count,
            "before_reads": self.before_reads,
            "after_reads": self.after_reads,
            "risk_level": self.risk_level,
            "summary": self.summary,
            "requires_approval": self.requires_approval,
            "executable": self.executable,
            "warnings": self.warnings,
        }


# ── Compiler registry ────────────────────────────────────────────────────────

CompilerFn = Callable[[SemanticMove, dict], CompiledPlan]
_COMPILERS: dict[str, CompilerFn] = {}


def register_compiler(move_id: str, fn: CompilerFn) -> None:
    """Register a compiler function for a specific move."""
    _COMPILERS[move_id] = fn


def register_family_compiler(family: str, fn: CompilerFn) -> None:
    """Register a fallback compiler for an entire move family."""
    _COMPILERS[f"__family__{family}"] = fn


def compile(move: SemanticMove, kernel: dict) -> CompiledPlan:
    """Compile a semantic move against a session kernel.

    Looks up the compiler by move_id first, then falls back to family compiler,
    then returns a non-executable plan with a warning.
    """
    # Try move-specific compiler
    fn = _COMPILERS.get(move.move_id)
    if fn:
        return fn(move, kernel)

    # Try family fallback
    fn = _COMPILERS.get(f"__family__{move.family}")
    if fn:
        return fn(move, kernel)

    # No compiler found — return a descriptive but non-executable plan
    return CompiledPlan(
        move_id=move.move_id,
        intent=move.intent,
        steps=[],
        summary=f"No compiler registered for move '{move.move_id}'. "
                f"The agent should interpret the intent and execute manually.",
        requires_approval=True,
        warnings=[f"No compiler for {move.move_id} — manual execution required"],
    )

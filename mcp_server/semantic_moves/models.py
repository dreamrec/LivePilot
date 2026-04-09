"""SemanticMove — high-level musical intent that compiles to tool sequences.

A semantic move expresses WHAT to achieve musically, not HOW to achieve it
parametrically. Each move has a compile_plan that decomposes into existing
deterministic MCP tools, and a verification_plan that checks the result.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SemanticMove:
    """A musical action expressed as intent, not parameters."""

    move_id: str
    family: str  # mix, arrangement, transition, sound_design, performance
    intent: str  # human-readable description of the musical goal
    targets: dict = field(default_factory=dict)  # dimension -> weight
    protect: dict = field(default_factory=dict)  # dimension -> threshold
    risk_level: str = "low"  # low, medium, high
    required_capabilities: list = field(default_factory=list)
    compile_plan: list = field(default_factory=list)  # [{tool, params, description}]
    verification_plan: list = field(default_factory=list)  # [{tool, check}]
    confidence: float = 0.7

    def to_dict(self) -> dict:
        return {
            "move_id": self.move_id,
            "family": self.family,
            "intent": self.intent,
            "targets": self.targets,
            "protect": self.protect,
            "risk_level": self.risk_level,
            "required_capabilities": self.required_capabilities,
            "compile_plan_steps": len(self.compile_plan),
            "confidence": self.confidence,
        }

    def to_full_dict(self) -> dict:
        """Full representation including compile and verification plans."""
        d = self.to_dict()
        d["compile_plan"] = self.compile_plan
        d["verification_plan"] = self.verification_plan
        return d

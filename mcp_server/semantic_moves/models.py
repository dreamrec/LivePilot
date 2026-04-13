"""SemanticMove — high-level musical intent that compiles to tool sequences.

A semantic move expresses WHAT to achieve musically, not HOW to achieve it
parametrically. Each move has a plan_template (static metadata for discovery)
and is compiled at runtime through compiler.compile() for executable plans.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SemanticMove:
    """A musical action expressed as intent, not parameters."""

    move_id: str
    family: str  # mix, arrangement, transition, sound_design, performance, sample
    intent: str  # human-readable description of the musical goal
    targets: dict = field(default_factory=dict)  # dimension -> weight
    protect: dict = field(default_factory=dict)  # dimension -> threshold
    risk_level: str = "low"  # low, medium, high
    required_capabilities: list = field(default_factory=list)
    plan_template: list = field(default_factory=list)  # [{tool, params, description}] — static metadata, NOT runtime truth
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
            "plan_template_steps": len(self.plan_template),
            "confidence": self.confidence,
        }

    def to_full_dict(self) -> dict:
        """Full representation including plan template and verification plans."""
        d = self.to_dict()
        d["plan_template"] = self.plan_template
        d["verification_plan"] = self.verification_plan
        return d

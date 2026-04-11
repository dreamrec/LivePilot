"""Preview Studio data models — pure dataclasses, zero I/O."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class PreviewVariant:
    """One creative option in a preview set."""

    variant_id: str = ""
    label: str = ""  # "safe", "strong", "unexpected"
    intent: str = ""  # what this variant is trying to achieve
    novelty_level: float = 0.0  # 0=conservative, 1=radical
    songbrain_delta: str = ""  # what changed vs identity
    taste_fit: float = 0.5  # 0-1 how well it matches user taste
    render_ref: str = ""  # reference to cached render
    summary: str = ""  # one-line musical explanation

    # What changed, why it matters, what it preserves
    what_changed: str = ""
    why_it_matters: str = ""
    what_preserved: str = ""

    # Move / plan data
    move_id: str = ""
    compiled_plan: Optional[dict] = None

    # Scoring
    score: float = 0.0
    identity_effect: str = "preserves"  # preserves, evolves, contrasts, resets

    # State
    status: str = "pending"  # pending, rendered, committed, discarded
    preview_mode: str = ""  # audible_preview, metadata_only_preview, analytical_preview
    created_at_ms: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        # Remove None compiled_plan for cleaner output
        if d.get("compiled_plan") is None:
            d.pop("compiled_plan", None)
        return d


@dataclass
class PreviewSet:
    """A set of variants tied to one user request."""

    set_id: str = ""
    request_text: str = ""
    strategy: str = "creative_triptych"  # creative_triptych, binary, custom
    source_kernel_id: str = ""
    variants: list[PreviewVariant] = field(default_factory=list)
    comparison: Optional[dict] = None
    committed_variant_id: str = ""
    status: str = "pending"  # pending, compared, committed, discarded
    created_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_dict(self) -> dict:
        return {
            "set_id": self.set_id,
            "request_text": self.request_text,
            "strategy": self.strategy,
            "source_kernel_id": self.source_kernel_id,
            "variants": [v.to_dict() for v in self.variants],
            "comparison": self.comparison,
            "committed_variant_id": self.committed_variant_id,
            "status": self.status,
            "variant_count": len(self.variants),
        }

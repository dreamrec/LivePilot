# mcp_server/atlas/overlays.py
"""User-local atlas overlay loader (v1.23.0).

Generalizes the v1.22.0 BUNDLED_ATLAS_PATH / USER_ATLAS_PATH pattern to
support arbitrary user-local namespaces of YAML overlay entries
(machines, signature chains, aesthetic lineages, techniques) under
~/.livepilot/atlas-overlays/<namespace>/.

Per spec: docs/superpowers/specs/2026-04-25-user-local-extensions-design.md
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class OverlayEntry:
    """A single overlay entity loaded from a YAML file under a namespace.

    Field names mirror the spec §5.1. `entity_id` (not `id`) avoids
    shadowing the Python `id()` builtin and matches the
    `OverlayIndex.get(namespace, entity_id)` accessor signature.

    For entity_type='signature_chain', `tags` and `artists` are required
    (the search ranker hits them). The loader enforces this — see
    `_validate_entry` (added in a later task).
    """
    namespace: str
    entity_type: str
    entity_id: str
    name: str
    description: str
    tags: list[str] = field(default_factory=list)
    artists: list[str] = field(default_factory=list)
    requires_box: Optional[str] = None
    body: dict = field(default_factory=dict)

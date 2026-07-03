"""Shared filesystem roots for LivePilot persistence."""

from __future__ import annotations

import os
from pathlib import Path


def livepilot_home() -> Path:
    """Return the root directory for user-scoped LivePilot state.

    ``LIVEPILOT_HOME`` exists primarily for tests and preview harnesses. Runtime
    defaults stay at ``~/.livepilot``.
    """
    value = os.environ.get("LIVEPILOT_HOME")
    if value and value.strip():
        return Path(value).expanduser()
    return Path.home() / ".livepilot"


def livepilot_projects_dir() -> Path:
    return livepilot_home() / "projects"


def livepilot_memory_dir() -> Path:
    return livepilot_home() / "memory"

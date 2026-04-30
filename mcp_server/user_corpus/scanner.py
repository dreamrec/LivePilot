"""Scanner abstract base class + registry.

A Scanner reads ONE file of its type (e.g. one .als, one .adg, one .amxd) and
returns a JSON-serializable sidecar dict. It also derives searchable tags +
description from that sidecar so the corpus runner can build a YAML wrapper.

Plug in your own:

    from mcp_server.user_corpus.scanner import Scanner, register_scanner

    @register_scanner
    class MyScanner(Scanner):
        type_id = "my-format"
        file_extensions = [".myx"]
        output_subdir = "my_format"

        def scan_one(self, path):
            return {"data": ...}

        def derive_tags(self, sidecar):
            return ["my-format", "..."]

        def derive_description(self, sidecar):
            return "..."

The decorator self-registers in the global SCANNERS dict; the runner discovers
it automatically as long as the module is imported somewhere.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar


class Scanner(ABC):
    """Per-file content scanner.

    Subclasses must define:
      type_id           — unique short id, e.g. "als"
      file_extensions   — list of lowercase extensions, e.g. [".als"]
      output_subdir     — where sidecars land under the output root, e.g. "projects"
      schema_version    — bump when sidecar shape changes (defaults to 1)

    And implement:
      scan_one(path)             — parse one file → dict
      derive_tags(sidecar)       — searchable tags
      derive_description(sidecar)— human-readable one-liner

    Optional overrides:
      slug(path)         — how to name the sidecar file (default: lowercased stem)
      is_applicable(p)   — file-applicability predicate (default: extension match)
    """

    type_id: ClassVar[str]
    file_extensions: ClassVar[list[str]]
    output_subdir: ClassVar[str]
    schema_version: ClassVar[int] = 1

    @abstractmethod
    def scan_one(self, path: Path) -> dict:
        ...

    @abstractmethod
    def derive_tags(self, sidecar: dict) -> list[str]:
        ...

    @abstractmethod
    def derive_description(self, sidecar: dict) -> str:
        ...

    def is_applicable(self, path: Path) -> bool:
        return path.suffix.lower() in self.file_extensions

    def slug(self, path: Path) -> str:
        """Filesystem-safe slug derived from the file's stem.

        Lowercase, spaces and underscores → hyphens, strip the suffix.
        Override to disambiguate (e.g. include parent folder when filenames collide).
        """
        s = path.stem.lower()
        s = s.replace(" ", "-").replace("_", "-")
        return "-".join(part for part in s.split("-") if part)


# ─── Registry ────────────────────────────────────────────────────────────────

SCANNERS: dict[str, type[Scanner]] = {}


def register_scanner(cls: type[Scanner]) -> type[Scanner]:
    """Decorator: registers a Scanner subclass under its type_id.

    Idempotent — re-registering the same type_id silently overrides the prior
    registration (useful for hot-reload during development; do NOT depend on
    re-registration for production correctness).
    """
    if not issubclass(cls, Scanner):
        raise TypeError(f"{cls.__name__} is not a Scanner subclass")
    if not getattr(cls, "type_id", None):
        raise ValueError(f"{cls.__name__} must define type_id")
    SCANNERS[cls.type_id] = cls
    return cls


def get_scanner(type_id: str) -> Scanner:
    """Instantiate a registered scanner by type_id. Raises KeyError if missing."""
    cls = SCANNERS[type_id]
    return cls()


def list_scanners() -> list[str]:
    """Return all registered scanner type_ids in insertion order."""
    return list(SCANNERS.keys())

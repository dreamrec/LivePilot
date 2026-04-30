"""Manifest — declarative source registry for user corpus scans.

Schema lives in the YAML; this module is just (de)serialization + dataclasses.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


# ─── Default paths ───────────────────────────────────────────────────────────

DEFAULT_OUTPUT_ROOT = Path.home() / ".livepilot" / "atlas-overlays" / "user"
DEFAULT_MANIFEST_PATH = DEFAULT_OUTPUT_ROOT / "manifest.yaml"

CURRENT_SCHEMA_VERSION = 1


# ─── Data classes ────────────────────────────────────────────────────────────


@dataclass
class Source:
    """One declared scan source."""
    id: str
    type: str                           # scanner type_id
    path: str                           # filesystem path (may contain ~)
    recursive: bool = True
    exclude_globs: list[str] = field(default_factory=list)
    last_scanned: str | None = None     # ISO 8601 UTC, set by the runner
    file_count: int | None = None       # set by the runner after scan
    options: dict[str, Any] = field(default_factory=dict)

    @property
    def resolved_path(self) -> Path:
        return Path(os.path.expanduser(self.path)).resolve()

    def mark_scanned(self, file_count: int) -> None:
        self.last_scanned = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.file_count = file_count


@dataclass
class Manifest:
    """Top-level manifest — all scan sources + global options."""
    schema_version: int = CURRENT_SCHEMA_VERSION
    sources: list[Source] = field(default_factory=list)
    output: dict[str, Any] = field(default_factory=lambda: {
        "root": str(DEFAULT_OUTPUT_ROOT),
        "schema_version": CURRENT_SCHEMA_VERSION,
    })
    options: dict[str, Any] = field(default_factory=lambda: {
        "parallel_workers": 4,
        "skip_unchanged": True,
        "log_level": "info",
        "on_error": "continue",
    })
    ai_annotation: dict[str, Any] = field(default_factory=lambda: {
        "enabled": False,
        "model": "sonnet",
        "fields": [
            "sonic_fingerprint",
            "tags",
            "reach_for",
            "avoid",
            "cross_references",
        ],
    })

    @property
    def output_root(self) -> Path:
        return Path(os.path.expanduser(self.output.get("root", str(DEFAULT_OUTPUT_ROOT))))

    def find_source(self, source_id: str) -> Source | None:
        for s in self.sources:
            if s.id == source_id:
                return s
        return None

    def add_source(self, source: Source) -> None:
        if self.find_source(source.id):
            raise ValueError(f"Source id '{source.id}' already exists; remove or rename first")
        self.sources.append(source)

    def remove_source(self, source_id: str) -> Source | None:
        match = self.find_source(source_id)
        if match:
            self.sources.remove(match)
        return match


# ─── (De)serialization ───────────────────────────────────────────────────────


def load_manifest(path: Path = DEFAULT_MANIFEST_PATH) -> Manifest:
    """Load a manifest YAML. Returns a default Manifest if the file is missing."""
    if not path.exists():
        return Manifest()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sources = [Source(**s) for s in (raw.get("sources") or [])]
    return Manifest(
        schema_version=raw.get("schema_version", CURRENT_SCHEMA_VERSION),
        sources=sources,
        output=raw.get("output") or Manifest().output,
        options=raw.get("options") or Manifest().options,
        ai_annotation=raw.get("ai_annotation") or Manifest().ai_annotation,
    )


def save_manifest(manifest: Manifest, path: Path = DEFAULT_MANIFEST_PATH) -> None:
    """Persist a manifest as YAML. Creates parent dirs if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": manifest.schema_version,
        "sources": [
            {k: v for k, v in asdict(s).items() if v is not None and v != [] and v != {}}
            for s in manifest.sources
        ],
        "output": manifest.output,
        "options": manifest.options,
        "ai_annotation": manifest.ai_annotation,
    }
    path.write_text(
        yaml.dump(data, sort_keys=False, default_flow_style=False, width=200, allow_unicode=True),
        encoding="utf-8",
    )


def init_default_manifest(path: Path = DEFAULT_MANIFEST_PATH) -> Manifest:
    """Create a fresh manifest at the default path, ensuring directory exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return load_manifest(path)
    m = Manifest()
    save_manifest(m, path)
    return m

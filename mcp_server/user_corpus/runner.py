"""Scan runner — orchestrates per-file scans across all configured sources.

Reads a Manifest, walks each source's directory, dispatches to the registered
Scanner for that source's type_id, and writes:
  - <output_root>/<scanner.output_subdir>/_parses/<slug>.json   (full sidecar)
  - <output_root>/<scanner.output_subdir>/<slug>.yaml           (search wrapper)

Per-file errors are logged and counted but never abort the whole scan.
mtime-based incremental skipping is on by default.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import yaml

from .manifest import Manifest, Source, save_manifest
from .scanner import Scanner, get_scanner

logger = logging.getLogger(__name__)


# ─── Result types ────────────────────────────────────────────────────────────


@dataclass
class FileScanResult:
    path: Path
    sidecar_path: Path | None = None
    wrapper_path: Path | None = None
    skipped: bool = False
    error: str | None = None


@dataclass
class SourceScanResult:
    source_id: str
    type_id: str
    files_scanned: int = 0
    files_skipped: int = 0
    files_errored: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)  # (path, msg)
    elapsed_sec: float = 0.0


@dataclass
class ScanResult:
    sources: list[SourceScanResult] = field(default_factory=list)
    total_scanned: int = 0
    total_skipped: int = 0
    total_errored: int = 0


# ─── Entry point ─────────────────────────────────────────────────────────────


def run_scan(
    manifest: Manifest,
    only_source_id: str | None = None,
    update_manifest_path: Path | None = None,
) -> ScanResult:
    """Run scans for every source in the manifest (or just one if filtered).

    Always writes sidecars + wrappers to the output root. Returns a ScanResult
    aggregating per-source counts. If `update_manifest_path` is provided, the
    runner persists `last_scanned` + `file_count` updates to disk.
    """
    skip_unchanged = bool(manifest.options.get("skip_unchanged", True))
    output_root = manifest.output_root

    overall = ScanResult()
    for src in manifest.sources:
        if only_source_id and src.id != only_source_id:
            continue
        try:
            scanner = get_scanner(src.type)
        except KeyError:
            logger.warning(
                "No scanner registered for type_id=%s (source %s) — skipping",
                src.type, src.id,
            )
            continue
        ssr = _scan_source(src, scanner, output_root, skip_unchanged)
        overall.sources.append(ssr)
        overall.total_scanned += ssr.files_scanned
        overall.total_skipped += ssr.files_skipped
        overall.total_errored += ssr.files_errored

        # Update the source's metadata
        src.mark_scanned(file_count=ssr.files_scanned + ssr.files_skipped)

    if update_manifest_path is not None:
        save_manifest(manifest, update_manifest_path)
    return overall


# ─── Per-source scan ─────────────────────────────────────────────────────────


def _scan_source(
    source: Source,
    scanner: Scanner,
    output_root: Path,
    skip_unchanged: bool,
) -> SourceScanResult:
    import time
    t0 = time.time()
    ssr = SourceScanResult(source_id=source.id, type_id=source.type)

    src_path = source.resolved_path
    if not src_path.exists():
        ssr.errors.append((str(src_path), "Source path does not exist"))
        return ssr

    excludes = source.exclude_globs or []
    files = list(_iter_files(src_path, scanner, source.recursive, excludes))

    sub_root = output_root / scanner.output_subdir
    parses_dir = sub_root / "_parses"
    parses_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        try:
            slug = f"{source.id}__{scanner.slug(f)}"
            sidecar_path = parses_dir / f"{slug}.json"
            wrapper_path = sub_root / f"{slug}.yaml"

            if skip_unchanged and _is_up_to_date(f, sidecar_path):
                ssr.files_skipped += 1
                continue

            sidecar = _build_sidecar(scanner, f, source)
            sidecar_path.write_text(
                json.dumps(sidecar, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            wrapper = _build_wrapper(scanner, source, sidecar, sidecar_path)
            wrapper_path.write_text(
                yaml.dump(wrapper, sort_keys=False, default_flow_style=False,
                          width=200, allow_unicode=True),
                encoding="utf-8",
            )
            ssr.files_scanned += 1
        except Exception as e:  # noqa: BLE001 — never abort over one bad file
            ssr.files_errored += 1
            ssr.errors.append((str(f), f"{type(e).__name__}: {e}"))
            logger.warning("Scan error %s: %s", f, e)

    ssr.elapsed_sec = round(time.time() - t0, 2)
    return ssr


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _iter_files(
    root: Path, scanner: Scanner, recursive: bool, excludes: list[str],
) -> Iterable[Path]:
    """Yield files matching scanner extensions, honoring excludes + recursion.

    Filters out:
      - macOS AppleDouble metadata files (filenames starting with "._")
      - Hidden files (filenames starting with ".") — usually OS/cache cruft
      - Anything matching a caller-supplied exclude_glob
    """
    walker = root.rglob("*") if recursive else root.glob("*")
    for p in walker:
        if not p.is_file():
            continue
        # Skip macOS resource-fork siblings and hidden files
        if p.name.startswith("._") or p.name.startswith("."):
            continue
        if not scanner.is_applicable(p):
            continue
        if any(p.match(g) for g in excludes):
            continue
        yield p


def _is_up_to_date(source_file: Path, sidecar_path: Path) -> bool:
    """True iff the sidecar exists AND its source mtime matches what's recorded."""
    if not sidecar_path.exists():
        return False
    try:
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return False
    recorded_mtime = sidecar.get("source_mtime")
    if recorded_mtime is None:
        return False
    try:
        return int(recorded_mtime) == int(source_file.stat().st_mtime)
    except OSError:
        return False


def _build_sidecar(scanner: Scanner, path: Path, source: Source) -> dict:
    """Run the scanner + wrap with provenance metadata."""
    data = scanner.scan_one(path)
    return {
        "schema_version": scanner.schema_version,
        "scanner": scanner.type_id,
        "source_id": source.id,
        "source_path": str(path),
        "source_mtime": int(path.stat().st_mtime),
        "source_sha256": _sha256_short(path),
        "scan_timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data": data,
    }


def _sha256_short(path: Path, chunk: int = 1 << 20) -> str:
    """First 16 hex chars of SHA-256. Cheap fingerprint for change detection."""
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            while True:
                buf = fh.read(chunk)
                if not buf:
                    break
                h.update(buf)
        return h.hexdigest()[:16]
    except OSError:
        return ""


def _build_wrapper(
    scanner: Scanner, source: Source, sidecar: dict, sidecar_path: Path,
) -> dict:
    """Build the searchable YAML wrapper that the overlay loader indexes."""
    data = sidecar.get("data") or {}
    slug = sidecar_path.stem
    namespace = f"user.{source.id}"
    return {
        "entity_id": slug,
        "entity_type": f"user_{scanner.type_id}",
        "namespace": namespace,
        "name": data.get("name") or sidecar_path.stem,
        "description": scanner.derive_description(data),
        "tags": _common_tags(source, scanner) + scanner.derive_tags(data),
        "sidecar_path": str(sidecar_path.relative_to(sidecar_path.parent.parent)),
        "schema_version": scanner.schema_version,
    }


def _common_tags(source: Source, scanner: Scanner) -> list[str]:
    """Tags every wrapper gets regardless of scanner type."""
    return [
        f"scanner:{scanner.type_id}",
        f"source:{source.id}",
        f"namespace:user.{source.id}",
    ]

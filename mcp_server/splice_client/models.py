"""Splice client data models — Python representations of Splice gRPC messages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SpliceSample:
    """A sample from the Splice catalog or local library."""

    file_hash: str = ""
    filename: str = ""
    local_path: str = ""          # empty if not downloaded
    audio_key: str = ""           # lowercase: "c#", "a", "eb"
    chord_type: str = ""          # "major", "minor", ""
    bpm: int = 0
    duration_ms: int = 0
    genre: str = ""
    sample_type: str = ""         # "loop" or "oneshot"
    tags: list[str] = field(default_factory=list)
    provider_name: str = ""
    pack_uuid: str = ""
    popularity: int = 0
    is_premium: bool = False
    preview_url: str = ""
    waveform_url: str = ""
    is_downloaded: bool = False

    @property
    def key_display(self) -> str:
        """Normalized key: 'c#' + 'minor' → 'C#m'."""
        if not self.audio_key:
            return ""
        key = self.audio_key[0].upper() + self.audio_key[1:]
        if self.chord_type.lower() in ("minor", "min"):
            key += "m"
        return key

    @property
    def duration_seconds(self) -> float:
        return self.duration_ms / 1000.0 if self.duration_ms else 0.0

    def to_dict(self) -> dict:
        return {
            "file_hash": self.file_hash,
            "filename": self.filename,
            "local_path": self.local_path,
            "key": self.key_display,
            "audio_key_raw": self.audio_key,
            "chord_type": self.chord_type,
            "bpm": self.bpm,
            "duration": self.duration_seconds,
            "genre": self.genre,
            "sample_type": self.sample_type,
            "tags": self.tags,
            "provider": self.provider_name,
            "pack_uuid": self.pack_uuid,
            "popularity": self.popularity,
            "is_downloaded": self.is_downloaded,
            "is_premium": self.is_premium,
        }


@dataclass
class SpliceSearchResult:
    """Result from a Splice catalog search."""

    total_hits: int = 0
    samples: list[SpliceSample] = field(default_factory=list)
    matching_tags: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total_hits": self.total_hits,
            "sample_count": len(self.samples),
            "samples": [s.to_dict() for s in self.samples],
            "matching_tags": self.matching_tags,
        }


@dataclass
class SpliceCredits:
    """User credit status."""

    credits: int = 0
    username: str = ""
    plan: str = ""

    def to_dict(self) -> dict:
        return {
            "credits": self.credits,
            "username": self.username,
            "plan": self.plan,
        }

"""Corpus Intelligence Layer — structured knowledge from device-knowledge markdown.

Parses the device-knowledge corpus (creative-thinking.md, automation-as-music.md,
effects-*.md, instruments-synths.md, chains-genre.md) into queryable Python
structures. This gives sound_design critics, wonder_mode engine, and other
modules access to deep creative knowledge at runtime — not just LLM guidance.

Lazy-loaded at first access; pure computation, no I/O after initial load.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ── Data structures ─────────────────────────────────────────────────────


@dataclass
class EmotionalRecipe:
    """Maps an emotion/quality to specific technical actions."""
    emotion: str = ""
    techniques: list[str] = field(default_factory=list)
    parameters: dict[str, str] = field(default_factory=dict)  # param_hint -> value_hint


@dataclass
class PhysicalModelRecipe:
    """Maps a physical material (water, metal, glass) to device chains."""
    material: str = ""
    devices: list[str] = field(default_factory=list)
    techniques: list[str] = field(default_factory=list)


@dataclass
class AutomationGesture:
    """A multi-parameter automation macro gesture."""
    name: str = ""
    description: str = ""
    parameters: list[dict] = field(default_factory=list)  # [{param, from, to}]
    duration_bars: str = ""


@dataclass
class GenreChain:
    """A complete effect chain recipe for a genre."""
    genre: str = ""
    devices: list[str] = field(default_factory=list)
    parameter_hints: dict[str, str] = field(default_factory=dict)
    description: str = ""


@dataclass
class DeviceKnowledge:
    """Deep knowledge about a specific Ableton device."""
    device_name: str = ""
    category: str = ""  # synth, effect, spectral, etc.
    techniques: list[str] = field(default_factory=list)
    sweet_spots: dict[str, str] = field(default_factory=dict)
    anti_patterns: list[str] = field(default_factory=list)


@dataclass
class Corpus:
    """The full parsed corpus — queryable from any module."""
    emotional_recipes: dict[str, EmotionalRecipe] = field(default_factory=dict)
    physical_models: dict[str, PhysicalModelRecipe] = field(default_factory=dict)
    automation_gestures: dict[str, AutomationGesture] = field(default_factory=dict)
    genre_chains: dict[str, GenreChain] = field(default_factory=dict)
    device_knowledge: dict[str, DeviceKnowledge] = field(default_factory=dict)
    anti_patterns: list[str] = field(default_factory=list)

    # ── Query methods ───────────────────────────────────────────────

    def suggest_for_emotion(self, emotion: str) -> Optional[EmotionalRecipe]:
        """Find techniques for an emotional quality (warmth, tension, etc.)."""
        emotion_lower = emotion.lower()
        if emotion_lower in self.emotional_recipes:
            return self.emotional_recipes[emotion_lower]
        # Fuzzy: check if emotion is a substring of any key
        for key, recipe in self.emotional_recipes.items():
            if emotion_lower in key or key in emotion_lower:
                return recipe
        return None

    def suggest_for_material(self, material: str) -> Optional[PhysicalModelRecipe]:
        """Find device chains for a physical material quality."""
        return self.physical_models.get(material.lower())

    def get_gesture(self, name: str) -> Optional[AutomationGesture]:
        """Get a named automation macro gesture."""
        return self.automation_gestures.get(name.lower())

    def get_genre_chain(self, genre: str) -> Optional[GenreChain]:
        """Get a genre-specific effect chain recipe."""
        genre_lower = genre.lower()
        if genre_lower in self.genre_chains:
            return self.genre_chains[genre_lower]
        for key, chain in self.genre_chains.items():
            if genre_lower in key or key in genre_lower:
                return chain
        return None

    def get_device(self, name: str) -> Optional[DeviceKnowledge]:
        """Get deep knowledge about a specific device."""
        return self.device_knowledge.get(name.lower())

    def recommend_modulation_for_device(self, device_name: str) -> list[str]:
        """Given a device, suggest what to modulate based on corpus knowledge."""
        dk = self.get_device(device_name)
        if dk and dk.techniques:
            return dk.techniques[:5]
        return []

    def get_automation_density_for_section(self, section_type: str) -> dict:
        """Return recommended automation parameter count + rate for a section type."""
        density_map = {
            "intro": {"param_count": "1-2", "rate": "very slow (0.05-0.1 Hz)", "purpose": "establish mood"},
            "build": {"param_count": "3-5", "rate": "accelerating exponential", "purpose": "create tension"},
            "peak": {"param_count": "5-8", "rate": "mixed slow + rhythmic", "purpose": "maximum energy"},
            "breakdown": {"param_count": "1-2", "rate": "very slow, gentle", "purpose": "breathing room"},
            "outro": {"param_count": "1-2", "rate": "gradually reducing", "purpose": "return to start"},
        }
        return density_map.get(section_type.lower(), density_map["peak"])


# ── Parser ──────────────────────────────────────────────────────────────


def _find_corpus_dir() -> Optional[str]:
    """Find the device-knowledge corpus directory."""
    # Check in the skill references (repo path)
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", "livepilot", "skills",
                     "livepilot-core", "references", "device-knowledge"),
        # Also check plugin cache paths
        os.path.expanduser("~/.claude/plugins/livepilot/skills/livepilot-core/references/device-knowledge"),
    ]
    for path in candidates:
        if os.path.isdir(path):
            return path
    return None


def _parse_emotional_section(text: str) -> dict[str, EmotionalRecipe]:
    """Parse the emotional-to-technical mapping section."""
    recipes: dict[str, EmotionalRecipe] = {}
    current_emotion = ""
    current_techniques: list[str] = []

    for line in text.split("\n"):
        line = line.strip()
        # New emotion header: ### Tension & Anxiety
        if line.startswith("### "):
            if current_emotion and current_techniques:
                recipes[current_emotion.lower()] = EmotionalRecipe(
                    emotion=current_emotion,
                    techniques=current_techniques,
                )
            current_emotion = line[4:].strip()
            current_techniques = []
        elif line.startswith("- **") and current_emotion:
            # Extract technique: - **High-resonance filter sweep** — description
            technique = line.lstrip("- ")
            current_techniques.append(technique)

    # Don't forget the last one
    if current_emotion and current_techniques:
        recipes[current_emotion.lower()] = EmotionalRecipe(
            emotion=current_emotion,
            techniques=current_techniques,
        )

    return recipes


def _parse_physical_models(text: str) -> dict[str, PhysicalModelRecipe]:
    """Parse the physical world modeling section."""
    models: dict[str, PhysicalModelRecipe] = {}
    current_material = ""
    current_techniques: list[str] = []
    current_devices: list[str] = []

    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("### "):
            if current_material:
                models[current_material.lower()] = PhysicalModelRecipe(
                    material=current_material,
                    devices=current_devices,
                    techniques=current_techniques,
                )
            current_material = line[4:].strip()
            current_techniques = []
            current_devices = []
        elif line.startswith("- **") and current_material:
            # Extract device name from bold
            match = re.match(r"- \*\*(.+?)\*\*", line)
            if match:
                dev_name = match.group(1)
                current_devices.append(dev_name)
            current_techniques.append(line.lstrip("- "))

    if current_material:
        models[current_material.lower()] = PhysicalModelRecipe(
            material=current_material,
            devices=current_devices,
            techniques=current_techniques,
        )

    return models


def _parse_automation_gestures(text: str) -> dict[str, AutomationGesture]:
    """Parse the macro gesture section from automation-as-music.md."""
    gestures: dict[str, AutomationGesture] = {}
    current_name = ""
    current_desc = ""
    current_params: list[dict] = []

    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("### The ") and "Gesture" in line:
            if current_name:
                gestures[current_name.lower()] = AutomationGesture(
                    name=current_name,
                    description=current_desc,
                    parameters=current_params,
                )
            # Extract name: ### The "Open Up" Gesture
            match = re.search(r'"(.+?)"', line)
            current_name = match.group(1) if match else line[4:].strip()
            current_desc = ""
            current_params = []
        elif line.startswith("- **") and current_name:
            # Parameter hint: - **Filter cutoff:** 30% -> 65%
            current_params.append({"raw": line.lstrip("- ")})
        elif line.startswith("- **Musical meaning:**"):
            current_desc = line.replace("- **Musical meaning:**", "").strip()

    if current_name:
        gestures[current_name.lower()] = AutomationGesture(
            name=current_name,
            description=current_desc,
            parameters=current_params,
        )

    return gestures


def _parse_genre_chains(text: str) -> dict[str, GenreChain]:
    """Parse genre chain recipes from chains-genre.md."""
    chains: dict[str, GenreChain] = {}
    current_genre = ""
    current_devices: list[str] = []
    current_desc = ""

    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("### ") or line.startswith("## "):
            if current_genre and current_devices:
                chains[current_genre.lower()] = GenreChain(
                    genre=current_genre,
                    devices=current_devices,
                    description=current_desc,
                )
            header = line.lstrip("#").strip()
            current_genre = header
            current_devices = []
            current_desc = ""
        elif line.startswith("- **") and current_genre:
            match = re.match(r"- \*\*(.+?)\*\*", line)
            if match:
                current_devices.append(match.group(1))
        elif line and not line.startswith("-") and not line.startswith("#") and current_genre and not current_desc:
            current_desc = line

    if current_genre and current_devices:
        chains[current_genre.lower()] = GenreChain(
            genre=current_genre,
            devices=current_devices,
            description=current_desc,
        )

    return chains


def _read_file(path: str) -> str:
    """Read a file, returning empty string on failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return ""


def load_corpus() -> Corpus:
    """Load and parse the full device-knowledge corpus."""
    corpus_dir = _find_corpus_dir()
    if not corpus_dir:
        return Corpus()  # Empty corpus — no files found

    corpus = Corpus()

    # Parse creative-thinking.md
    ct_text = _read_file(os.path.join(corpus_dir, "creative-thinking.md"))
    if ct_text:
        # Split by Part headers
        parts = re.split(r"## Part \d+:", ct_text)
        for part in parts:
            if "Emotional-to-Technical" in part:
                corpus.emotional_recipes = _parse_emotional_section(part)
            elif "Physical World" in part:
                corpus.physical_models = _parse_physical_models(part)
            elif "Anti-Patterns" in part:
                # Extract anti-pattern names
                for line in part.split("\n"):
                    if line.strip().startswith("### The ") and "Trap" in line:
                        corpus.anti_patterns.append(line.strip().lstrip("# "))

    # Parse automation-as-music.md
    auto_text = _read_file(os.path.join(corpus_dir, "automation-as-music.md"))
    if auto_text:
        parts = re.split(r"## Part \d+:", auto_text)
        for part in parts:
            if "Multi-Parameter" in part or "Macro Gesture" in part:
                corpus.automation_gestures = _parse_automation_gestures(part)

    # Parse chains-genre.md
    genre_text = _read_file(os.path.join(corpus_dir, "chains-genre.md"))
    if genre_text:
        corpus.genre_chains = _parse_genre_chains(genre_text)

    # Parse instrument and effect knowledge files
    for filename in ["instruments-synths.md", "effects-distortion.md",
                     "effects-space.md", "effects-spectral.md"]:
        file_text = _read_file(os.path.join(corpus_dir, filename))
        if file_text:
            current_device = ""
            current_techniques: list[str] = []
            for line in file_text.split("\n"):
                line = line.strip()
                if line.startswith("## ") or line.startswith("### "):
                    if current_device and current_techniques:
                        corpus.device_knowledge[current_device.lower()] = DeviceKnowledge(
                            device_name=current_device,
                            category=filename.replace(".md", ""),
                            techniques=current_techniques,
                        )
                    current_device = line.lstrip("#").strip()
                    current_techniques = []
                elif line.startswith("- **") and current_device:
                    current_techniques.append(line.lstrip("- "))
            if current_device and current_techniques:
                corpus.device_knowledge[current_device.lower()] = DeviceKnowledge(
                    device_name=current_device,
                    category=filename.replace(".md", ""),
                    techniques=current_techniques,
                )

    return corpus


# ── Module-level lazy singleton ─────────────────────────────────────────

_corpus_instance: Optional[Corpus] = None


def get_corpus() -> Corpus:
    """Get the global corpus instance (lazy-loaded on first call)."""
    global _corpus_instance
    if _corpus_instance is None:
        _corpus_instance = load_corpus()
    return _corpus_instance

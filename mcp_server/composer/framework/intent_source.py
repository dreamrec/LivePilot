"""Abstract source of CompositionIntent — prompt-derived, session-derived, or hybrid."""
from abc import ABC, abstractmethod
from typing import Any


class IntentSource(ABC):
    """Abstract base — produces a CompositionIntent for any of the 3 compose modes."""

    @abstractmethod
    def parse(self, ctx: Any) -> dict:
        """Return a CompositionIntent-shaped dict. Stub returns {}."""
        ...


class PromptSource(IntentSource):
    """Phase 1 stub — full impl in Task 5. Will wrap prompt_parser.parse_prompt."""

    def __init__(self, prompt: str):
        self.prompt = prompt

    def parse(self, ctx: Any) -> dict:
        return {}


class SessionSource(IntentSource):
    """Phase 1 stub — full impl in Task 5. Will introspect live Ableton session."""

    def __init__(self, scene_index: int = 0):
        self.scene_index = scene_index

    def parse(self, ctx: Any) -> dict:
        return {}


class HybridSource(IntentSource):
    """Phase 1 stub — full impl in Task 5. Combines prompt + session."""

    def __init__(self, prompt: str, scene_index: int = 0):
        self.prompt = prompt
        self.scene_index = scene_index

    def parse(self, ctx: Any) -> dict:
        return {}

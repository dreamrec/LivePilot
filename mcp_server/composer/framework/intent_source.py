"""Abstract source of CompositionIntent — prompt-derived, session-derived, or hybrid.

PromptSource: parses a free-text prompt via prompt_parser.parse_prompt
SessionSource: introspects the live Ableton session via the MCP tool layer
HybridSource: combines both — session wins on tempo/key, prompt wins on genre/mood
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)


class IntentSource(ABC):
    """Abstract base — produces a CompositionIntent-shaped dict for any compose mode.

    Returned dict shape (CompositionIntent fields):
        {
          "genre": str,
          "mood": str,
          "tempo": int,
          "key": str,
          "sub_genre": str,
          "descriptors": list,
          "explicit_elements": list,
          "energy": float,
          "layer_count": int,
          "duration_bars": int,
          # ... see prompt_parser.CompositionIntent for full list
        }
    """

    @abstractmethod
    def parse(self, ctx: Any) -> dict:
        ...


class PromptSource(IntentSource):
    """Parses a free-text prompt via prompt_parser.parse_prompt."""

    def __init__(self, prompt: str):
        self.prompt = prompt

    def parse(self, ctx: Any) -> dict:
        # Lazy import to avoid circular deps at framework-package import time
        from ..prompt_parser import parse_prompt
        intent = parse_prompt(self.prompt)
        # CompositionIntent has its own to_dict(); prefer it, else fall back to asdict
        if hasattr(intent, "to_dict"):
            return intent.to_dict()
        if hasattr(intent, "__dataclass_fields__"):
            from dataclasses import asdict
            return asdict(intent)
        if isinstance(intent, dict):
            return intent
        # Fallback for unexpected return type
        return {"raw_intent": str(intent)}


class SessionSource(IntentSource):
    """Introspects the live Ableton session via MCP tools.

    Reads session tempo, key, time signature, and per-track content.
    Returns the same CompositionIntent shape as PromptSource so downstream
    consumers don't care which source was used.
    """

    def __init__(self, scene_index: int = 0):
        self.scene_index = scene_index

    def parse(self, ctx: Any) -> dict:
        ableton = ctx.lifespan_context.get("ableton") if hasattr(ctx, "lifespan_context") else None
        if ableton is None:
            logger.warning("SessionSource.parse: ableton client not in ctx — returning empty intent")
            return {}

        try:
            session = ableton.send_command("get_session_info", {})
        except Exception as exc:
            logger.warning("SessionSource.parse: get_session_info failed: %s", exc)
            return {}

        intent: dict = {
            "tempo": float(session.get("tempo", 120.0)),
            "scene_index": self.scene_index,
        }

        # Time signature
        sig_num = session.get("signature_numerator")
        sig_den = session.get("signature_denominator")
        if sig_num and sig_den:
            intent["time_signature"] = f"{sig_num}/{sig_den}"

        # Try to read song scale (Live 12.4 song-scale API)
        try:
            scale_result = ableton.send_command("get_song_scale", {})
            if scale_result and not scale_result.get("error"):
                intent["key"] = scale_result.get("root_note") or scale_result.get("key")
                intent["scale_mode"] = scale_result.get("scale_name") or scale_result.get("mode")
        except Exception as exc:
            logger.debug("SessionSource.parse: get_song_scale unavailable: %s", exc)

        return intent


class HybridSource(IntentSource):
    """Combines prompt + session intent.

    Merge rule:
    - tempo: session wins (live truth) if present, else prompt
    - key/scale_mode: session wins if present, else prompt
    - genre/mood: prompt wins (creative directive)
    - other fields: prompt wins, session fills gaps
    """

    def __init__(self, prompt: str, scene_index: int = 0):
        self.prompt = prompt
        self.scene_index = scene_index

    def parse(self, ctx: Any) -> dict:
        prompt_intent = PromptSource(self.prompt).parse(ctx)
        session_intent = SessionSource(self.scene_index).parse(ctx)

        merged = dict(prompt_intent)  # start with prompt as base
        # Session-wins overrides
        for session_authoritative in ("tempo", "key", "scale_mode", "time_signature"):
            session_val = session_intent.get(session_authoritative)
            if session_val is not None:
                merged[session_authoritative] = session_val
        # Carry session-only fields the prompt doesn't have
        for k, v in session_intent.items():
            if k not in merged:
                merged[k] = v
        return merged

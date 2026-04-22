from __future__ import annotations

import asyncio
from types import SimpleNamespace

from mcp_server.sample_engine import tools
from mcp_server.splice_client.models import PlanKind, SpliceSample, SpliceSearchResult


class _ReconnectableSpliceClient:
    def __init__(self):
        self.connected = False
        self.connect_calls = 0
        self.search_calls = 0

    async def connect(self):
        self.connect_calls += 1
        self.connected = True
        return True

    async def get_credits(self):
        return SimpleNamespace(
            username="tester",
            plan="subscribed",
            plan_kind=PlanKind.ABLETON_LIVE,
            sounds_plan_id=12,
            features={"ableton_unmetered": True},
            user_uuid="user-123",
            credits=80,
        )

    async def search_samples(self, **kwargs):
        self.search_calls += 1
        return SpliceSearchResult(
            total_hits=1,
            samples=[
                SpliceSample(
                    file_hash="hash-123",
                    filename="lofi_chord.wav",
                    audio_key="Cm",
                    bpm=90,
                    sample_type="loop",
                    provider_name="Test Pack",
                    preview_url="https://example.com/preview.mp3",
                )
            ],
        )


def test_get_splice_credits_reconnects_stale_client():
    client = _ReconnectableSpliceClient()
    ctx = SimpleNamespace(lifespan_context={"splice_client": client})

    result = asyncio.run(tools.get_splice_credits(ctx))

    assert result["connected"] is True
    assert result["username"] == "tester"
    assert client.connect_calls == 1


def test_splice_catalog_hunt_reconnects_stale_client():
    client = _ReconnectableSpliceClient()
    ctx = SimpleNamespace(lifespan_context={"splice_client": client})

    result = asyncio.run(tools.splice_catalog_hunt(ctx, query="lofi chord"))

    assert result["connected"] is True
    assert result["total_hits"] == 1
    assert result["samples"][0]["file_hash"] == "hash-123"
    assert client.connect_calls == 1
    assert client.search_calls == 1


def test_search_samples_uses_reconnected_grpc_before_sql_fallback():
    client = _ReconnectableSpliceClient()
    ctx = SimpleNamespace(lifespan_context={"splice_client": client})

    result = asyncio.run(
        tools.search_samples(ctx, query="lofi chord", source="splice", max_results=5)
    )

    assert result["result_count"] == 1
    assert result["results"][0]["splice_catalog"] is True
    assert result["results"][0]["file_hash"] == "hash-123"
    assert client.connect_calls == 1
    assert client.search_calls == 1

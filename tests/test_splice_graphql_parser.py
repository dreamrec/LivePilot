"""Tests for the Splice GraphQL SamplesSearch response parser.

The parser normalizes Splice's GraphQL envelope into the flat shape
LivePilot's MCP tools return. Broken parser = broken `splice_describe_sound`
everywhere downstream, so we lock the shape here.

Fixtures are stripped-down subsets of the real 2026-04-22 capture. The
full capture lives in docs/research/splice-api-capture/ (gitignored).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from mcp_server.splice_client.http_bridge import (
    SpliceHTTPError,
    _load_graphql_query,
    _parse_samples_search,
    _parse_similar_sounds,
    _flatten_sample_item,
)


# ── Fixtures ─────────────────────────────────────────────────────────


def _sample_asset(uuid: str, name: str, **kwargs) -> dict:
    """Factory for a minimal SampleAsset-shaped dict."""
    base = {
        "uuid": uuid,
        "name": name,
        "liked": False,
        "licensed": False,
        "asset_type": {"label": "Sample", "__typename": "AssetType"},
        "asset_type_slug": "sample",
        "bundled_content_daws": [],
        "tags": [],
        "files": [],
        "__typename": "SampleAsset",
        "bpm": 95,
        "chord_type": None,
        "duration": 10105,
        "instrument": None,
        "key": None,
        "asset_category_slug": "loop",
        "has_similar_sounds": True,
        "has_coso": True,
        "attributes": [],
    }
    base.update(kwargs)
    return base


def _minimal_valid_response() -> dict:
    """Minimum-shape GraphQL response for the happy path."""
    return {
        "data": {
            "assetsSearch": {
                "items": [
                    _sample_asset("uuid-1", "kick.wav", bpm=120,
                                  tags=[{"label": "drums", "uuid": "t1"}]),
                    _sample_asset("uuid-2", "hat.wav", bpm=140,
                                  tags=[{"label": "drums", "uuid": "t1"},
                                        {"label": "techno", "uuid": "t2"}]),
                ],
                "__typename": "AssetPage",
                "tag_summary": [
                    {"tag": {"label": "drums", "uuid": "t1"}, "count": 3416,
                     "__typename": "TagSummary"},
                    {"tag": {"label": "techno", "uuid": "t2"}, "count": 562,
                     "__typename": "TagSummary"},
                ],
                "device_summary": None,
                "rephrased_query_string": "drums",
                "extracted_filter_by": None,
                "pagination_metadata": {"currentPage": 1, "totalPages": 82},
                "response_metadata": {"next": None, "previous": None,
                                      "records": 4100},
            }
        }
    }


# ── Happy-path parsing ───────────────────────────────────────────────


def test_parses_minimum_valid_response():
    out = _parse_samples_search(_minimal_valid_response())
    assert len(out["samples"]) == 2
    assert out["total_hits"] == 4100
    assert out["rephrased_query_string"] == "drums"


def test_samples_flatten_tags_to_labels():
    out = _parse_samples_search(_minimal_valid_response())
    first = out["samples"][0]
    # tags list in output is just label strings, not full tag dicts
    assert first["tags"] == ["drums"]
    second = out["samples"][1]
    assert second["tags"] == ["drums", "techno"]


def test_samples_preserve_core_fields():
    out = _parse_samples_search(_minimal_valid_response())
    s = out["samples"][0]
    assert s["uuid"] == "uuid-1"
    assert s["name"] == "kick.wav"
    assert s["bpm"] == 120
    # duration preserved from fixture default
    assert s["duration"] == 10105
    # liked/licensed coerced to booleans
    assert s["liked"] is False
    assert s["licensed"] is False


def test_pagination_metadata_surfaces():
    out = _parse_samples_search(_minimal_valid_response())
    assert out["current_page"] == 1
    assert out["total_pages"] == 82


def test_tag_summary_flattened():
    out = _parse_samples_search(_minimal_valid_response())
    ts = out["tag_summary"]
    assert len(ts) == 2
    labels = {t["label"] for t in ts}
    assert "drums" in labels
    # counts preserved
    counts = {t["label"]: t["count"] for t in ts}
    assert counts["drums"] == 3416


# ── Error handling ───────────────────────────────────────────────────


def test_graphql_errors_raise_structured_exception():
    errored_response = {
        "errors": [
            {"message": "Rate limit exceeded", "path": ["assetsSearch"]}
        ]
    }
    with pytest.raises(SpliceHTTPError) as exc_info:
        _parse_samples_search(errored_response)
    assert exc_info.value.code == "GRAPHQL_ERROR"
    assert "Rate limit" in exc_info.value.message


def test_missing_data_block_returns_empty_not_crash():
    out = _parse_samples_search({})
    assert out["samples"] == []
    assert out["total_hits"] == 0


def test_non_dict_input_returns_empty():
    out = _parse_samples_search("not a dict")
    assert out["samples"] == []


def test_missing_items_returns_empty_samples():
    out = _parse_samples_search({"data": {"assetsSearch": {}}})
    assert out["samples"] == []


# ── Parent/pack extraction ───────────────────────────────────────────


def test_pack_name_extracted_from_parents():
    item = _sample_asset("u1", "x.wav")
    item["parents"] = {
        "items": [
            {"uuid": "pack-1", "name": "Vintage Rhythm Machines",
             "__typename": "PackAsset"}
        ]
    }
    response = {"data": {"assetsSearch": {"items": [item]}}}
    out = _parse_samples_search(response)
    assert out["samples"][0]["pack_name"] == "Vintage Rhythm Machines"


def test_missing_parents_returns_none_pack_name():
    out = _parse_samples_search(_minimal_valid_response())
    # no parents in the fixture items → pack_name is None
    assert out["samples"][0]["pack_name"] is None


# ── Query loading ────────────────────────────────────────────────────


def test_load_graphql_query_returns_content():
    q = _load_graphql_query("samples_search")
    assert "SamplesSearch" in q
    assert "assetsSearch" in q
    assert len(q) > 1000  # real query is ~5938 chars


def test_load_graphql_query_caches():
    q1 = _load_graphql_query("samples_search")
    q2 = _load_graphql_query("samples_search")
    # Same object — cache returns the exact string instance
    assert q1 is q2


def test_load_graphql_query_missing_raises_clear_error():
    with pytest.raises(FileNotFoundError) as exc_info:
        _load_graphql_query("nonexistent_operation")
    assert "nonexistent_operation" in str(exc_info.value)
    # Actionable message includes capture instructions
    assert "mitmproxy" in str(exc_info.value) or "capture" in str(exc_info.value).lower()


def test_load_asset_similar_sounds_query():
    """Variations capture from 2026-04-22 — the AssetSimilarSoundsQuery
    should be loadable the same way."""
    q = _load_graphql_query("asset_similar_sounds")
    assert "AssetSimilarSoundsQuery" in q
    assert "similarSounds" in q
    assert "$uuid: GUID!" in q
    # Around 886 chars in the capture
    assert 500 < len(q) < 2000


# ── Parse similar-sounds (Variations) ────────────────────────────────


def _similar_sounds_response(items=None) -> dict:
    """Factory for the AssetSimilarSoundsQuery GraphQL envelope."""
    return {"data": {"similarSounds": items or []}}


def test_parse_similar_sounds_empty_list():
    out = _parse_similar_sounds(_similar_sounds_response([]))
    assert out["similar_samples"] == []
    assert out["count"] == 0


def test_parse_similar_sounds_flattens_items():
    items = [
        _sample_asset("sim-1", "kick_loop.wav", bpm=125,
                      tags=[{"label": "drums", "uuid": "t1"}]),
        _sample_asset("sim-2", "hat_loop.wav", bpm=140),
    ]
    out = _parse_similar_sounds(_similar_sounds_response(items))
    assert out["count"] == 2
    assert out["similar_samples"][0]["uuid"] == "sim-1"
    assert out["similar_samples"][0]["tags"] == ["drums"]
    assert out["similar_samples"][1]["uuid"] == "sim-2"
    assert out["similar_samples"][1]["bpm"] == 140


def test_parse_similar_sounds_graphql_errors_raise():
    errored = {"errors": [{"message": "Asset not found",
                          "path": ["similarSounds"]}]}
    with pytest.raises(SpliceHTTPError) as exc_info:
        _parse_similar_sounds(errored)
    assert exc_info.value.code == "GRAPHQL_ERROR"
    assert "Asset not found" in exc_info.value.message


def test_parse_similar_sounds_missing_data_returns_empty():
    out = _parse_similar_sounds({})
    assert out["similar_samples"] == []
    assert out["count"] == 0


def test_parse_similar_sounds_non_list_response_is_safe():
    # If the server returns a single object instead of a list for some
    # reason, don't crash — return empty.
    out = _parse_similar_sounds({"data": {"similarSounds": None}})
    assert out["similar_samples"] == []


# ── Shared flattener ────────────────────────────────────────────────


def test_flatten_sample_item_happy_path():
    item = _sample_asset("u1", "x.wav", bpm=120, key="am",
                         tags=[{"label": "synth"}])
    flat = _flatten_sample_item(item)
    assert flat["uuid"] == "u1"
    assert flat["name"] == "x.wav"
    assert flat["bpm"] == 120
    assert flat["key"] == "am"
    assert flat["tags"] == ["synth"]


def test_flatten_sample_item_non_dict_returns_empty():
    assert _flatten_sample_item("not-a-dict") == {}
    assert _flatten_sample_item(None) == {}


def test_flatten_used_consistently_between_search_and_similar():
    """Shape invariant: a sample appearing in both endpoints should
    flatten to identical dicts. This is why we use one flattener."""
    item = _sample_asset("shared-uuid", "sample.wav", bpm=100)
    search_response = {"data": {"assetsSearch": {"items": [item]}}}
    similar_response = _similar_sounds_response([item])
    search_out = _parse_samples_search(search_response)["samples"][0]
    sim_out = _parse_similar_sounds(similar_response)["similar_samples"][0]
    assert search_out == sim_out

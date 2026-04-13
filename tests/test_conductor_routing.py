"""Tests for conductor sample-aware routing (Phase 2)."""
import pytest
from mcp_server.tools._conductor import classify_request


def test_sample_request_routes_to_sample_engine():
    plan = classify_request("find me a dark vocal sample")
    assert plan.routes[0].engine == "sample_engine"


def test_slice_request_routes_to_sample_engine():
    plan = classify_request("slice this loop into percussion hits")
    assert plan.routes[0].engine == "sample_engine"


def test_splice_request_routes_to_sample_engine():
    plan = classify_request("search my Splice library for a techno kick")
    assert plan.routes[0].engine == "sample_engine"


def test_chop_request_routes_to_sample_engine():
    plan = classify_request("chop this break and flip it")
    assert plan.routes[0].engine == "sample_engine"


def test_one_shot_routes_to_sample_engine():
    plan = classify_request("load a one-shot percussion hit")
    assert plan.routes[0].engine == "sample_engine"


def test_foley_routes_to_sample_engine():
    plan = classify_request("find me some foley sounds")
    assert plan.routes[0].engine == "sample_engine"


def test_mixed_arrangement_sample_routes_multi():
    plan = classify_request("find a vocal chop and build a hook for the chorus")
    engines = [r.engine for r in plan.routes]
    assert "sample_engine" in engines


def test_pure_mix_does_not_route_to_sample():
    plan = classify_request("clean up the muddy low mids")
    assert plan.routes[0].engine == "mix_engine"


def test_sample_workflow_mode():
    plan = classify_request("find me a warm pad sample")
    assert plan.workflow_mode in ("sample_discovery", "slice_workflow", "sample_plus_arrangement")


def test_slice_workflow_mode():
    plan = classify_request("slice this break into transient hits")
    assert plan.workflow_mode == "slice_workflow"


def test_arrangement_plus_sample_workflow():
    plan = classify_request("find a sample and arrange it into the verse")
    assert plan.workflow_mode == "sample_plus_arrangement"

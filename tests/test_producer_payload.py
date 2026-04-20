"""Tests for producer_payload threading on BranchSeed + ExperimentBranch (PR1).

Covers:
  - default schema_version is always set
  - callers that pass no payload get the default
  - callers that pass a payload have schema_version preserved / injected
  - payload survives to_dict round-trip
  - ExperimentBranch surfaces producer_payload as both nested (seed) and
    top-level shortcut
  - mutable default isolation (two BranchSeeds can't share a payload dict)
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.branches import (
    BranchSeed,
    PRODUCER_PAYLOAD_SCHEMA_VERSION,
    seed_from_move_id,
    freeform_seed,
    analytical_seed,
)
from mcp_server.experiment.models import ExperimentBranch


class TestDefaults:

    def test_seed_has_schema_version_by_default(self):
        seed = BranchSeed(seed_id="s", source="freeform")
        assert seed.producer_payload == {"schema_version": PRODUCER_PAYLOAD_SCHEMA_VERSION}

    def test_seed_from_move_id_payload_defaults(self):
        seed = seed_from_move_id("make_punchier")
        assert seed.producer_payload["schema_version"] == PRODUCER_PAYLOAD_SCHEMA_VERSION

    def test_freeform_seed_payload_defaults(self):
        seed = freeform_seed(seed_id="f", hypothesis="h")
        assert seed.producer_payload["schema_version"] == PRODUCER_PAYLOAD_SCHEMA_VERSION

    def test_analytical_seed_payload_defaults(self):
        seed = analytical_seed(seed_id="a", hypothesis="h")
        assert seed.producer_payload["schema_version"] == PRODUCER_PAYLOAD_SCHEMA_VERSION

    def test_mutable_default_isolation(self):
        # Regression guard — two seeds must NOT share a payload dict.
        a = BranchSeed(seed_id="a", source="freeform")
        b = BranchSeed(seed_id="b", source="freeform")
        a.producer_payload["custom_key"] = "custom_value"
        assert "custom_key" not in b.producer_payload


class TestCustomPayload:

    def test_semantic_seed_accepts_custom_payload(self):
        seed = seed_from_move_id(
            "widen_pad",
            producer_payload={"origin": "wonder_assembly", "rank": 1},
        )
        assert seed.producer_payload["origin"] == "wonder_assembly"
        assert seed.producer_payload["rank"] == 1
        # schema_version is still injected
        assert seed.producer_payload["schema_version"] == PRODUCER_PAYLOAD_SCHEMA_VERSION

    def test_synthesis_seed_payload_shape(self):
        seed = freeform_seed(
            seed_id="syn_1",
            hypothesis="Wavetable morph",
            source="synthesis",
            producer_payload={
                "device_name": "Wavetable",
                "track_index": 3,
                "device_index": 0,
                "strategy": "osc_position_shift",
            },
        )
        p = seed.producer_payload
        assert p["device_name"] == "Wavetable"
        assert p["strategy"] == "osc_position_shift"
        assert p["schema_version"] == PRODUCER_PAYLOAD_SCHEMA_VERSION

    def test_composer_seed_payload_carries_intent(self):
        intent_dict = {
            "genre": "techno",
            "tempo": 128,
            "energy": 0.7,
        }
        seed = freeform_seed(
            seed_id="cmp_1",
            hypothesis="Composer canonical",
            source="composer",
            producer_payload={
                "strategy": "canonical",
                "intent": intent_dict,
            },
        )
        assert seed.producer_payload["strategy"] == "canonical"
        assert seed.producer_payload["intent"] == intent_dict

    def test_caller_supplied_schema_version_preserved(self):
        # If a producer knows about a future schema version, don't overwrite.
        seed = freeform_seed(
            seed_id="future",
            hypothesis="h",
            producer_payload={"schema_version": 99, "exotic": True},
        )
        assert seed.producer_payload["schema_version"] == 99
        assert seed.producer_payload["exotic"] is True

    def test_empty_dict_gets_default_version(self):
        seed = freeform_seed(seed_id="e", hypothesis="h", producer_payload={})
        assert seed.producer_payload["schema_version"] == PRODUCER_PAYLOAD_SCHEMA_VERSION


class TestSerialization:

    def test_to_dict_includes_producer_payload(self):
        seed = freeform_seed(
            seed_id="s",
            hypothesis="h",
            source="synthesis",
            producer_payload={"device_name": "Drift", "strategy": "filter_sweep"},
        )
        d = seed.to_dict()
        assert "producer_payload" in d
        assert d["producer_payload"]["device_name"] == "Drift"
        assert d["producer_payload"]["schema_version"] == PRODUCER_PAYLOAD_SCHEMA_VERSION

    def test_to_dict_injects_missing_schema_version_on_output(self):
        # Defensive: if someone mutates payload to strip schema_version,
        # to_dict still emits one so downstream never sees a payload
        # without a version.
        seed = freeform_seed(seed_id="s", hypothesis="h")
        seed.producer_payload = {"only_key": "value"}
        d = seed.to_dict()
        assert d["producer_payload"]["schema_version"] == PRODUCER_PAYLOAD_SCHEMA_VERSION

    def test_experiment_branch_surfaces_payload_top_level(self):
        seed = freeform_seed(
            seed_id="s",
            hypothesis="h",
            source="composer",
            producer_payload={"strategy": "energy_shift", "intent": {"genre": "ambient"}},
        )
        branch = ExperimentBranch.from_seed(seed=seed, branch_id="b1")
        d = branch.to_dict()
        assert "producer_payload" in d
        assert d["producer_payload"]["strategy"] == "energy_shift"
        # Also still under the nested seed for producers that want the full shape
        assert d["seed"]["producer_payload"]["strategy"] == "energy_shift"

    def test_experiment_branch_legacy_construction_gets_default_payload(self):
        # A branch built without a seed (legacy move-only construction)
        # has seed=None and no producer_payload top-level key.
        branch = ExperimentBranch(branch_id="b", name="b", move_id="make_punchier")
        d = branch.to_dict()
        assert "producer_payload" not in d  # absent when no seed

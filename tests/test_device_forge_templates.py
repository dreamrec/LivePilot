"""Tests for gen~ DSP template library."""

from __future__ import annotations

import pytest

from mcp_server.device_forge.templates import (
    get_template,
    list_templates,
    list_categories,
    TEMPLATES,
)
from mcp_server.device_forge.models import GenExprTemplate


class TestTemplateRegistry:
    def test_templates_not_empty(self):
        assert len(TEMPLATES) >= 10

    def test_list_templates_returns_dicts(self):
        items = list_templates()
        assert all(isinstance(t, dict) for t in items)
        assert all("template_id" in t for t in items)

    def test_list_by_category(self):
        chaos = list_templates(category="chaos")
        assert len(chaos) >= 1
        assert all(t["category"] == "chaos" for t in chaos)

    def test_get_template_by_id(self):
        t = get_template("lorenz_attractor")
        assert t is not None
        assert isinstance(t, GenExprTemplate)
        assert "History" in t.code

    def test_get_nonexistent_returns_none(self):
        assert get_template("nonexistent_xyz") is None

    def test_list_categories(self):
        cats = list_categories()
        assert "chaos" in cats
        assert "delay" in cats
        assert "distortion" in cats

    def test_all_templates_have_valid_code(self):
        for t in TEMPLATES.values():
            assert "out1" in t.code, f"{t.template_id} has no output"

    def test_all_templates_have_descriptions(self):
        for t in TEMPLATES.values():
            assert len(t.description) > 10, f"{t.template_id} missing description"


class TestSpecificTemplates:
    def test_lorenz_has_params(self):
        t = get_template("lorenz_attractor")
        param_names = [p.name for p in t.params]
        assert "sigma" in param_names
        assert "speed" in param_names

    def test_karplus_strong_has_freq_param(self):
        t = get_template("karplus_strong")
        param_names = [p.name for p in t.params]
        assert "freq" in param_names

    def test_wavefolder_has_drive(self):
        t = get_template("wavefolder")
        param_names = [p.name for p in t.params]
        assert "drive" in param_names

    def test_bitcrusher_has_rate_or_bits(self):
        t = get_template("bitcrusher")
        param_names = [p.name for p in t.params]
        assert "rate" in param_names or "bits" in param_names

    def test_fdn_has_feedback(self):
        t = get_template("feedback_delay_network")
        param_names = [p.name for p in t.params]
        assert "feedback" in param_names

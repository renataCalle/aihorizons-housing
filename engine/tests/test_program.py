"""Scoring a requested building type (analyze(..., program=...))."""

import json
from pathlib import Path

import pytest

from navigator_contracts import SiteAnalysis
from navigator_engine import analyze

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "golden" / "site_context"


def _ctx(name: str) -> dict:
    return json.loads((GOLDEN / f"{name}.json").read_text())


def test_default_is_unchanged_by_the_new_argument() -> None:
    ctx = _ctx("clean_by_right")
    assert analyze(ctx) == analyze(ctx, program=None)


def test_requested_building_is_the_only_option() -> None:
    a = analyze(_ctx("clean_by_right"), program={"product_type": "duplex"})
    SiteAnalysis.model_validate(a)
    assert [(o["product_type"], o["units"]) for o in a["options"]] == [("duplex", 2)]
    assert a["metrics"]["option"] == a["options"][0]["label"]


def test_a_building_the_rules_rule_out_is_high_risk_with_the_reason() -> None:
    a = analyze(_ctx("steep_slope"), program={"product_type": "walkup"})  # R1D-M
    SiteAnalysis.model_validate(a)
    assert a["options"] == [] and a["metrics"] is None
    assert a["verdict"]["band"] == "high_risk"
    assert "rule out" in a["verdict"]["headline"]


def test_unknown_requests_are_errors() -> None:
    with pytest.raises(ValueError, match="unknown product_type"):
        analyze(_ctx("clean_by_right"), program={"product_type": "tower"})
    with pytest.raises(ValueError, match="tested at"):
        analyze(_ctx("clean_by_right"), program={"product_type": "townhome", "units": 40})

"""Contract conformance: every golden fixture validates against its contract."""

import json
from pathlib import Path

import pytest

from navigator_contracts import SCHEMA_VERSION, SiteAnalysis, SiteContext

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "golden"
CONTEXTS = sorted((GOLDEN / "site_context").glob("*.json"))
ANALYSES = sorted((GOLDEN / "site_analysis").glob("*.json"))


@pytest.mark.parametrize("path", CONTEXTS, ids=lambda p: p.stem)
def test_site_context_fixture_validates(path: Path) -> None:
    ctx = SiteContext.model_validate_json(path.read_text())
    assert ctx.schema_version == SCHEMA_VERSION


@pytest.mark.parametrize("path", ANALYSES, ids=lambda p: p.stem)
def test_site_analysis_fixture_validates(path: Path) -> None:
    a = SiteAnalysis.model_validate_json(path.read_text())
    if a.verdict.score is not None:  # the components add up to the score
        assert abs(sum(c.points for c in a.verdict.components) - a.verdict.score) <= 2


def test_every_context_has_an_analysis() -> None:
    assert {p.stem for p in CONTEXTS} == {p.stem for p in ANALYSES}
    assert len(CONTEXTS) == 8


def test_unknown_fields_are_rejected() -> None:
    raw = json.loads(CONTEXTS[0].read_text())
    raw["surprise"] = 1
    with pytest.raises(ValueError):
        SiteContext.model_validate(raw)


@pytest.mark.parametrize("path", ANALYSES, ids=lambda p: p.stem)
def test_rule_checks_explain_the_options(path: Path) -> None:
    """Each headline option appears in the rule table with the same relief, and a building
    that passes every rule is allowed outright with certainty."""
    a = SiteAnalysis.model_validate_json(path.read_text())
    if a.rule_checks is None:
        assert a.options == []
        return
    by_label = {p.chosen_as: p for p in a.rule_checks.programs if p.chosen_as}
    for opt in a.options:
        prog = by_label[opt.label]
        assert (prog.product_type, prog.units) == (opt.product_type, opt.units)
        failed = [c for c in prog.checks if c.status in ("needs_approval", "rejected")]
        assert len(failed) == len(opt.relief)
    for prog in a.rule_checks.programs:
        if prog.outcome == "by_right":
            assert all(c.status in ("pass", "not_applicable") for c in prog.checks)
            assert prog.approval_prob.p50 == 1.0
        if prog.outcome == "rejected":
            assert prog.approval_prob is None

"""Approval routes, zoning code references and zoning board precedents in the analysis."""

import copy
import json
from pathlib import Path

import pytest

from navigator_engine import analyze, code
from navigator_engine.precedents import similar_cases

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "golden" / "site_context"
NAMES = sorted(p.stem for p in GOLDEN.glob("*.json"))


def _ctx(name: str) -> dict:
    return json.loads((GOLDEN / f"{name}.json").read_text())


@pytest.mark.parametrize("name", NAMES)
def test_options_needing_approvals_link_a_step(name: str) -> None:
    a = analyze(_ctx(name))
    orders = {s["order"]: s for s in a["next_steps"]}
    for o in a["options"]:
        if o["relief"]:
            assert o["resolution"] and o["resolution"].startswith("Needs ")
            assert orders[o["resolved_by_step"]]["action"] == "Zoning pre-application meeting"
        else:
            assert o["resolution"] is None and o["resolved_by_step"] is None


@pytest.mark.parametrize("name", NAMES)
def test_code_rule_evidence_has_a_date_and_link(name: str) -> None:
    a = analyze(_ctx(name))
    for f in a["flags"]:
        for e in f["evidence"]:
            if e["layer"] == "rules":
                assert e["as_of"] == code.CODE_AS_OF.isoformat() and e["url"]
    assert a["versions"]["ruleset_as_of"] == code.CODE_AS_OF.isoformat()


@pytest.mark.parametrize("name", NAMES)
def test_every_cited_section_is_in_the_glossary(name: str) -> None:
    a = analyze(_ctx(name))
    listed = {c["section"] for c in a["code_sections"]}
    for f in a["flags"]:
        for e in f["evidence"]:
            assert set(code.sections_in(e["code_section"])) <= listed
    for o in a["options"]:
        for r in o["relief"]:
            assert set(code.sections_in(r)) <= listed
    assert all(c["url"] and c["as_of"] for c in a["code_sections"])


def test_section_numbers_are_parsed_from_citations() -> None:
    assert code.sections_in("906.05.B.2 / 913.02.B") == ["906.05.B.2", "913.02.B"]
    assert code.sections_in("variance (903.03)") == ["903.03"]
    assert code.sections_in("911.04.A.69A") == ["911.04.A.69A"]
    assert code.sections_in("911.04.A.69(a)(1)") == ["911.04.A.69(a)(1)"]
    assert code._parents("906.02.F.2.a") == ["906.02.F.2.a", "906.02.F.2", "906.02.F", "906.02"]


CASES = [
    {"case_id": "near-same", "relief_types": ["variance"], "district": "R2-L",
     "decision_date": "2025-06-01", "distance_ft": 900.0},
    {"case_id": "other-type", "relief_types": ["special_exception"], "district": "R2-L",
     "decision_date": "2025-06-01", "distance_ft": 900.0},
    {"case_id": "other-district", "relief_types": ["variance"], "district": "RM-M",
     "decision_date": "2025-06-01", "distance_ft": 900.0},
    {"case_id": "far", "relief_types": ["Variance"], "district": "R2-M",
     "decision_date": "2025-06-01", "distance_ft": 4_000.0},
    {"case_id": "old", "relief_types": ["variance"], "district": "R2-H",
     "decision_date": "2014-01-01", "distance_ft": 500.0},
    {"case_id": "same-base", "relief_types": ["variance", "special exception"],
     "district": "R2-H", "decision_date": "2022-02-01", "distance_ft": 2_000.0},
]  # fmt: skip


def test_similar_cases_follow_the_rule() -> None:
    ctx = {"zba_cases_nearby": copy.deepcopy(CASES)}
    assert similar_cases(ctx, ["variance"], "R2-L") == ["near-same", "same-base"]
    assert similar_cases(ctx, ["special_exception"], "R2-L") == ["other-type", "same-base"]


def test_similar_cases_are_none_when_unavailable_or_not_needed() -> None:
    assert similar_cases({"zba_cases_nearby": None}, ["variance"], "R2-L") is None
    assert similar_cases({"zba_cases_nearby": CASES}, ["administrator_exception"], "R2-L") is None
    assert similar_cases({"zba_cases_nearby": []}, ["variance"], "R2-L") == []


@pytest.mark.parametrize("name", NAMES)
def test_every_cited_section_has_a_summary(name: str) -> None:
    missing = [c["section"] for c in analyze(_ctx(name))["code_sections"] if not c["summary"]]
    assert not missing, f"add these to config/rules/code_sections.csv: {missing}"
